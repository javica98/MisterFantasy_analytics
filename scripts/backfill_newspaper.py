"""
backfill_newspaper.py
======================
Genera periodicos (articles/*.json + cards/*.json) para jornadas historicas
que nunca se generaron en su momento.

run_newspaper.py esta pensado para ejecucion diaria en vivo: siempre mira
"los ultimos N dias" de la temporada activa. Para rellenar jornadas pasadas
(de la temporada activa o de una ya archivada) hace falta apuntar cada
jornada a su propia ventana de fechas historica, por eso este script usa
generate_json_for_jornada() en vez de generate_json().

Uso:
    python scripts/backfill_newspaper.py
"""

import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.AI_newspaper.generate_json import generate_json_for_jornada
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
from src.utils import db as db_utils
from src.utils.config_loader import load_config
from src.utils.file_utils import safe_save_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

cfg = load_config()
NEWS_UTILS = cfg["paths"]["images"]["news_utils"]

# (temporada, jornadas a rellenar en orden, carpeta base de newspaper/json)
PLAN = [
    (
        "2025-26",
        list(range(1, 16)) + [37],
        ROOT_DIR / "archive" / "temporada_2025-26" / "newspaper" / "json",
    ),
    (
        "2026-27",
        [1, 2, 3],
        Path(cfg["paths"]["json"]["news"]),
    ),
]


def _load_season_frames(season: str):
    df_gw = db_utils.read_table("gameweek", temporada=season)
    df_clas = db_utils.read_table("clasificaciones", temporada=season)
    df_quin = db_utils.read_table("quiniela", temporada=season)
    df_merc = db_utils.read_table("ganancias_clean", temporada=season)
    df_clean = df_merc[df_merc["type"] == "transfer"].copy() if not df_merc.empty else df_merc

    df_gw = df_gw.copy()
    df_gw["Date"] = pd.to_datetime(df_gw["Date"], errors="coerce")
    return df_gw, df_clas, df_quin, df_clean


def backfill_jornada(
    season: str,
    jornada: int,
    json_dir: Path,
    df_clean: pd.DataFrame,
    df_gw: pd.DataFrame,
    df_clas: pd.DataFrame,
    df_quin: pd.DataFrame,
    fecha_transfers_start,
    fecha_jornada_end,
):
    events = generate_json_for_jornada(
        jornada, fecha_transfers_start, fecha_jornada_end, df_clean, df_gw, df_clas, df_quin
    )
    n_transfers = len(events.get("transfers", []))
    n_gw = len(events.get("gameweek", []))
    logger.info("  json: %d transfers, %d entradas de gameweek", n_transfers, n_gw)
    if n_transfers == 0 and n_gw == 0:
        return False, "sin transfers ni gameweek en la ventana"
    if n_gw == 0:
        logger.warning("  sin gameweek para esta jornada — el periodico no tendra MVPs ni resultados")

    prompt_json = generate_prompts(events)
    memory_query = build_memory_query(events)
    relevant_memories = retrieve_relevant_memories(memory_query, top_k=8, temporada=season)
    memory_context = format_memory_context(relevant_memories)
    prompt_txt = build_final_prompt(prompt_json["bloques"], events, memory_context)

    fichajes_cards = [b for b in prompt_json["bloques"] if b["evento"] == "Fichaje destacado"]
    mvp_cards = [b for b in prompt_json["bloques"] if b["evento"] == "MVP de la jornada"]
    portada_fichajes = fichajes_cards[0] if fichajes_cards else (mvp_cards[0] if mvp_cards else {"jugador": "", "equipo": ""})
    portada_jornada = mvp_cards[0] if mvp_cards else (fichajes_cards[0] if fichajes_cards else {"jugador": "", "equipo": ""})

    path_foto_fichajes = os.path.join(NEWS_UTILS, "Portada_Fichajes.jpg")
    path_foto_jornada = os.path.join(NEWS_UTILS, "Portada_Jornada.jpg")

    texto_generado = run_orchestrator(
        prompt=prompt_txt,
        portada_fichajes=portada_fichajes,
        portada_jornada=portada_jornada,
        path_fichajes=path_foto_fichajes,
        path_jornada=path_foto_jornada,
    )
    if texto_generado is None or not texto_generado.get("cards"):
        return False, "el orquestador no devolvio cards validas"

    articles_dir = json_dir / "articles"
    cards_dir = json_dir / "cards"
    safe_save_json(events, str(articles_dir / f"jornada_{jornada}_json.json"))
    safe_save_json(texto_generado, str(cards_dir / f"jornada_{jornada}_cards.json"))

    memories = build_memories(events, texto_generado, temporada=season)
    changed = upsert_memories(memories, DEFAULT_MEMORY_PATH)
    logger.info("  memoria: %d recuerdos (%d nuevos/actualizados)", len(memories), changed)
    return True, changed


def main():
    results = []
    total_changed = 0

    for season, jornadas, json_dir in PLAN:
        logger.info("### Temporada %s -> %s", season, json_dir)
        df_gw, df_clas, df_quin, df_clean = _load_season_frames(season)
        if df_gw.empty:
            logger.error("Sin datos de gameweek para %s, se omite toda la temporada", season)
            for jornada in jornadas:
                results.append((season, jornada, "SIN DATOS: gameweek vacio"))
            continue

        max_by_jornada = df_gw.groupby("Jornada")["Date"].max()
        min_by_jornada = df_gw.groupby("Jornada")["Date"].min()

        for jornada in jornadas:
            logger.info("--- %s jornada %d ---", season, jornada)
            if jornada not in max_by_jornada.index:
                logger.warning("  sin datos de gameweek para esta jornada, se omite")
                results.append((season, jornada, "SIN DATOS: sin filas de gameweek"))
                continue

            fecha_jornada_end = max_by_jornada[jornada].date()
            if (jornada - 1) in max_by_jornada.index:
                fecha_transfers_start = max_by_jornada[jornada - 1].date()
            else:
                fecha_transfers_start = (min_by_jornada[jornada] - timedelta(days=14)).date()

            articles_path = json_dir / "articles" / f"jornada_{jornada}_json.json"
            cards_path = json_dir / "cards" / f"jornada_{jornada}_cards.json"
            if articles_path.exists() and cards_path.exists():
                logger.info("  ya generado en un intento anterior, se omite (cache): %s", cards_path)
                results.append((season, jornada, "OK (cache)"))
                continue

            try:
                ok, info = backfill_jornada(
                    season, jornada, json_dir, df_clean, df_gw, df_clas, df_quin,
                    fecha_transfers_start, fecha_jornada_end,
                )
                if ok:
                    total_changed += info if isinstance(info, int) else 0
                    results.append((season, jornada, "OK"))
                else:
                    results.append((season, jornada, f"FALLO: {info}"))
            except Exception as e:
                logger.exception("  excepcion generando %s jornada %s", season, jornada)
                results.append((season, jornada, f"EXCEPCION: {e}"))

    if total_changed:
        logger.info("Reconstruyendo indice de embeddings de memoria...")
        rebuild_embedding_index()

    logger.info("=== Resumen backfill (%d jornadas) ===", len(results))
    for season, jornada, status in results:
        logger.info("  %s J%d: %s", season, jornada, status)

    failed = [r for r in results if not r[2].startswith("OK")]
    if failed:
        logger.error("%d de %d fallaron", len(failed), len(results))
        sys.exit(1)
    logger.info("Todas las jornadas se generaron correctamente.")


if __name__ == "__main__":
    main()
