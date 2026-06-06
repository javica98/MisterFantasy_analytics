"""
Genera ediciones históricas del periódico, una por jornada.

Uso:
    python scripts/run_backfill.py
    python scripts/run_backfill.py --from-jornada 22
    python scripts/run_backfill.py --from-jornada 22 --to-jornada 30
    python scripts/run_backfill.py --reset-memory
    python scripts/run_backfill.py --dry-run

Lógica:
  - Salta jornadas 1-15 (sin fechas reales en gameweek.csv).
  - Salta jornadas sin datos en gameweek.csv (ej. jornada 37).
  - Procesa en orden cronológico (por fecha_max de cada jornada).
  - Modo resume: si los dos PNGs de una jornada ya existen, la salta.
  - Actualiza la memoria RAG de forma incremental tras cada jornada.
"""

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

# ── Ajuste de entorno ─────────────────────────────────────────────────────────
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent
SRC_DIR = ROOT_DIR / "src"

for p in (ROOT_DIR, SRC_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.chdir(ROOT_DIR)

from src.AI_newspaper.generate_json import generate_json_for_jornada
from src.AI_newspaper.generate_pdf import create_pdf
from src.AI_newspaper.generate_prompt import build_final_prompt, generate_prompts
from src.agents.orchestrator_agent import run_orchestrator
from src.memory.embedding_store import build_memory_query, rebuild_embedding_index
from src.memory.memory_builder import build_memories
from src.memory.memory_store import (
    DEFAULT_MEMORY_PATH,
    format_memory_context,
    retrieve_relevant_memories,
    upsert_memories,
)
from src.utils.config_loader import load_config
from src.utils.file_utils import safe_read_csv, safe_save_json, safe_save_png, safe_save_text

# ── Configuración ─────────────────────────────────────────────────────────────
cfg = load_config()

log_level = getattr(logging, cfg.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
log_file = cfg.get("logging", {}).get("file", "logs/backfill.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Rutas de salida
JSON_DIR = Path(cfg["paths"]["json"]["news"])
IMG_DIR = Path(cfg["paths"]["images"]["news"])
NEWS_UTILS = Path(cfg["paths"]["images"]["news_utils"])
IMAGES_TEAMS_DIR = cfg["paths"]["images"]["teams_dir"]
DEFAULT_TEAM_IMAGE = cfg["paths"]["images"]["default_team"]

# Fecha límite para considerar que una jornada tiene fecha real
# Jornadas 1-15 tienen todas 2025-11-29 (carga masiva inicial)
BULK_LOAD_DATE = pd.Timestamp("2025-11-29")


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_jornadas_cronologicas(df_gameweek: pd.DataFrame) -> list[dict]:
    """
    Devuelve las jornadas con fechas reales, ordenadas cronológicamente
    por su fecha_max. Excluye las jornadas sin datos reales (ej. 1-15, 37).
    """
    df = df_gameweek.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Solo jornadas con algún partido posterior al bulk load inicial
    jornadas_reales = (
        df[df["Date"] > BULK_LOAD_DATE]
        .groupby("Jornada")
        .agg(fecha_min=("Date", "min"), fecha_max=("Date", "max"))
        .reset_index()
        .sort_values("fecha_max")
    )

    return jornadas_reales.to_dict("records")


def is_done(jornada_num: int) -> bool:
    """True si los dos PNGs de la jornada ya existen (modo resume)."""
    fichajes = IMG_DIR / f"jornada_{jornada_num:02d}_fichajes_news.png"
    jornada = IMG_DIR / f"jornada_{jornada_num:02d}_jornada_news.png"
    return fichajes.exists() and jornada.exists()


def reset_memory() -> None:
    """Borra el fichero de memorias y el índice de embeddings."""
    memory_file = Path(DEFAULT_MEMORY_PATH)
    index_file = memory_file.parent / "embedding_index.json"
    embeddings_file = memory_file.parent / "embeddings.npy"

    for f in (memory_file, index_file, embeddings_file):
        if f.exists():
            f.unlink()
            logger.info("Memoria borrada: %s", f)

    logger.info("Memoria RAG reseteada. El backfill construira el historico desde cero.")


# ── Rate-limit helpers ────────────────────────────────────────────────────────

class _RateLimitExhausted(Exception):
    def __init__(self, retries: int):
        self.retries = retries


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detecta errores 429 / ModelThrottledException de Gemini o Groq."""
    msg = str(exc)
    return "429" in msg or "Too Many Requests" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def _extract_retry_delay(exc: Exception, default: int = 60) -> int:
    """Extrae el número de segundos sugerido por la API en el mensaje de error."""
    match = re.search(r"retry[^\d]*(\d+)", str(exc), re.IGNORECASE)
    return int(match.group(1)) + 5 if match else default


def _process_with_retry(
    *,
    jornada_num: int,
    fecha_transfers_start,
    fecha_jornada_end,
    df_clean,
    df_gameweek,
    df_clasificacion,
    df_quinielas,
    max_retries: int = 3,
    inter_jornada_delay: int = 0,
) -> bool:
    """
    Llama a process_jornada con reintentos automáticos en caso de rate limit (429).
    Lanza _RateLimitExhausted si se agota max_retries.
    """
    for attempt in range(1, max_retries + 2):  # +2: max_retries reintentos extra
        try:
            result = process_jornada(
                jornada_num=jornada_num,
                fecha_transfers_start=fecha_transfers_start,
                fecha_jornada_end=fecha_jornada_end,
                df_clean=df_clean,
                df_gameweek=df_gameweek,
                df_clasificacion=df_clasificacion,
                df_quinielas=df_quinielas,
            )
            if inter_jornada_delay > 0:
                logger.info("Esperando %ds antes de la siguiente jornada...", inter_jornada_delay)
                time.sleep(inter_jornada_delay)
            return result
        except Exception as exc:
            if _is_rate_limit_error(exc):
                wait = _extract_retry_delay(exc)
                if attempt > max_retries:
                    raise _RateLimitExhausted(retries=max_retries) from exc
                logger.warning(
                    "J%02d rate limit (intento %d/%d). Esperando %ds...",
                    jornada_num, attempt, max_retries, wait,
                )
                time.sleep(wait)
            else:
                raise  # errores no relacionados con rate limit se propagan arriba


# ── Procesado de una jornada ──────────────────────────────────────────────────

def process_jornada(
    jornada_num: int,
    fecha_transfers_start,
    fecha_jornada_end,
    df_clean: pd.DataFrame,
    df_gameweek: pd.DataFrame,
    df_clasificacion: pd.DataFrame,
    df_quinielas: pd.DataFrame,
) -> bool:
    """
    Genera la edición completa de una jornada.
    Devuelve True si tiene éxito, False si falla.
    """
    tag = f"J{jornada_num:02d}"
    logger.info("=" * 60)
    logger.info("%s Iniciando — ventana transfers: %s → %s", tag, fecha_transfers_start, fecha_jornada_end)

    # 1. Generar JSON de datos
    logger.info("%s [1/5] Generando JSON de datos...", tag)
    daily_json = generate_json_for_jornada(
        jornada_num=jornada_num,
        fecha_transfers_start=fecha_transfers_start,
        fecha_jornada_end=fecha_jornada_end,
        df_clean=df_clean,
        df_gameweek=df_gameweek,
        df_clasificacion=df_clasificacion,
        df_quinielas=df_quinielas,
    )
    logger.info(
        "%s   transfers=%d  gameweek=%d",
        tag,
        len(daily_json["transfers"]),
        len(daily_json["gameweek"]),
    )

    json_path = JSON_DIR / f"jornada_{jornada_num:02d}_json.json"
    safe_save_json(daily_json, str(json_path))

    # 2. Construir prompt + recuperar memoria RAG
    logger.info("%s [2/5] Construyendo prompt...", tag)
    prompt_data = generate_prompts(daily_json)
    memory_query = build_memory_query(daily_json)
    relevant_memories = retrieve_relevant_memories(memory_query, top_k=8)
    memory_context = format_memory_context(relevant_memories)
    logger.info("%s   %d recuerdos RAG recuperados", tag, len(relevant_memories))

    prompt_final = build_final_prompt(prompt_data["bloques"], daily_json, memory_context)
    prompt_path = JSON_DIR / f"jornada_{jornada_num:02d}_prompt.txt"
    safe_save_text(prompt_final, str(prompt_path))

    # Determinar jugadores de portada
    fichajes_bloques = [b for b in prompt_data["bloques"] if b["evento"] == "Fichaje destacado"]
    mvp_bloques = [b for b in prompt_data["bloques"] if b["evento"] == "MVP de la jornada"]
    portada_fichajes = fichajes_bloques[0] if fichajes_bloques else (mvp_bloques[0] if mvp_bloques else {"jugador": "", "equipo": ""})
    portada_jornada = mvp_bloques[0] if mvp_bloques else (fichajes_bloques[0] if fichajes_bloques else {"jugador": "", "equipo": ""})

    path_foto_fichajes = str(NEWS_UTILS / "Portada_Fichajes.jpg")
    path_foto_jornada = str(NEWS_UTILS / "Portada_Jornada.jpg")

    # 3. Orquestador IA
    logger.info("%s [3/5] Llamando al OrchestratorAgent...", tag)
    cards = run_orchestrator(
        prompt=prompt_final,
        portada_fichajes=portada_fichajes,
        portada_jornada=portada_jornada,
        path_fichajes=path_foto_fichajes,
        path_jornada=path_foto_jornada,
    )

    if cards is None:
        logger.error("%s OrchestratorAgent no generó cards válidas. Abortando esta jornada.", tag)
        return False

    logger.info("%s   %d cards generadas", tag, len(cards.get("cards", [])))
    cards_path = JSON_DIR / f"jornada_{jornada_num:02d}_cards.json"
    safe_save_json(cards, str(cards_path))

    # 4. Actualizar memoria RAG
    logger.info("%s [4/5] Actualizando memoria RAG...", tag)
    memories = build_memories(daily_json, cards)
    changed = upsert_memories(memories, DEFAULT_MEMORY_PATH)
    logger.info("%s   %d memorias (%d nuevas/actualizadas)", tag, len(memories), changed)
    if changed:
        rebuild_embedding_index()

    # 5. Generar PNGs
    logger.info("%s [5/5] Generando PNGs...", tag)
    quiniela_json = daily_json["quinielas"]
    clasificacion_json = daily_json["clasificacion"]

    portada_f = create_pdf("Fichajes", cards, quiniela_json, str(NEWS_UTILS), IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)
    portada_j = create_pdf("Jornada", cards, clasificacion_json, str(NEWS_UTILS), IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)

    png_fichajes = IMG_DIR / f"jornada_{jornada_num:02d}_fichajes_news.png"
    png_jornada = IMG_DIR / f"jornada_{jornada_num:02d}_jornada_news.png"

    safe_save_png(portada_f, str(png_fichajes))
    safe_save_png(portada_j, str(png_jornada))

    logger.info("%s COMPLETADA", tag)
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backfill de ediciones históricas del periódico.")
    parser.add_argument("--from-jornada", type=int, default=None, metavar="N", help="Empezar desde la jornada N")
    parser.add_argument("--to-jornada", type=int, default=None, metavar="N", help="Terminar en la jornada N (inclusive)")
    parser.add_argument("--reset-memory", action="store_true", help="Borrar memoria RAG antes de empezar")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar qué jornadas se procesarían sin ejecutar nada")
    parser.add_argument("--delay", type=int, default=0, metavar="SEG", help="Segundos de espera entre jornadas (util para no quemar cuota)")
    parser.add_argument("--max-retries", type=int, default=3, metavar="N", help="Reintentos ante error 429 antes de parar (default: 3)")
    args = parser.parse_args()

    logger.info("Cargando CSVs...")
    df_gameweek = safe_read_csv(cfg["paths"]["csv"]["gameweek"])
    df_clean = safe_read_csv(cfg["paths"]["csv"]["notificaciones_clean"])
    df_clasificacion = safe_read_csv(cfg["paths"]["csv"]["clasificaciones"])
    df_quinielas = safe_read_csv(cfg["paths"]["csv"]["quiniela"])

    df_gameweek["Date"] = pd.to_datetime(df_gameweek["Date"], errors="coerce")
    df_clean["fecha"] = pd.to_datetime(df_clean["fecha"], errors="coerce")

    jornadas = get_jornadas_cronologicas(df_gameweek)
    logger.info("Jornadas con datos reales: %s", [int(j["Jornada"]) for j in jornadas])

    if args.reset_memory and not args.dry_run:
        reset_memory()

    # Estado de progreso
    ok, skipped, failed = [], [], []

    # Fecha de inicio de la ventana de transfers para la primera jornada real
    prev_fecha_max = BULK_LOAD_DATE.date()

    for jornada_info in jornadas:
        jornada_num = int(jornada_info["Jornada"])
        fecha_max = jornada_info["fecha_max"].date()

        # Filtros de rango
        if args.from_jornada and jornada_num < args.from_jornada:
            prev_fecha_max = fecha_max
            continue
        if args.to_jornada and jornada_num > args.to_jornada:
            break

        if args.dry_run:
            estado = "EXISTE" if is_done(jornada_num) else "PENDIENTE"
            logger.info(
                "DRY-RUN  J%02d  %s -> %s  [%s]",
                jornada_num,
                prev_fecha_max,
                fecha_max,
                estado,
            )
            prev_fecha_max = fecha_max
            continue

        # Modo resume
        if is_done(jornada_num):
            logger.info("J%02d ya existe, saltando (modo resume).", jornada_num)
            skipped.append(jornada_num)
            prev_fecha_max = fecha_max
            continue

        try:
            success = _process_with_retry(
                jornada_num=jornada_num,
                fecha_transfers_start=prev_fecha_max,
                fecha_jornada_end=fecha_max,
                df_clean=df_clean,
                df_gameweek=df_gameweek,
                df_clasificacion=df_clasificacion,
                df_quinielas=df_quinielas,
                max_retries=args.max_retries,
                inter_jornada_delay=args.delay,
            )
            if success:
                ok.append(jornada_num)
            else:
                failed.append(jornada_num)
        except _RateLimitExhausted as exc:
            logger.error("J%02d cuota de API agotada tras %d reintentos. Para el dia de hoy.", jornada_num, exc.retries)
            logger.warning("Reanuda manana con: python scripts/run_backfill.py --from-jornada %d", jornada_num)
            failed.append(jornada_num)
            break
        except Exception as exc:
            logger.error("J%02d ERROR inesperado: %s", jornada_num, exc, exc_info=True)
            failed.append(jornada_num)
            logger.warning("Puedes reanudar con: python scripts/run_backfill.py --from-jornada %d", jornada_num)
            # No actualizamos prev_fecha_max para que la siguiente ejecucion
            # use la misma ventana de transfers
            break

        prev_fecha_max = fecha_max

    # Resumen final
    logger.info("=" * 60)
    logger.info("BACKFILL COMPLETADO")
    logger.info("  OK:       %s", ok)
    logger.info("  Saltadas: %s", skipped)
    logger.info("  Fallidas: %s", failed)
    if failed:
        logger.warning("Reanuda con: python scripts/run_backfill.py --from-jornada %d", failed[0])


if __name__ == "__main__":
    main()
