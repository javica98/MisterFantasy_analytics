import sys
import os
import json
import logging
from pathlib import Path

import pandas as pd

# ── Ajuste de rutas ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.data.merge_notifications import merge_feed_cards_until_match
from src.data.merge_clasification import merge_clasifications
from src.data.extract_notificaciones import extraer_notificaciones
from src.data.extract_clasificacion import extraer_clasificaciones
from src.data.extract_mercado import extraer_mercado
from src.data.extract_jornadas import extraer_jornadas
from src.data.extract_subidas_bajadas import extraer_subidas_bajadas
from src.data.extract_gameweek import extraer_gameweek
from src.data.merge_gameweek import merge_gameweek
from src.data.extract_calendario import (
    anotar_fecha_partido, merge_partidos, parse_calendario, parse_partidos, seleccionar_jornadas,
)
from src.data.extract_quinielas import extraer_quinielas
from src.data.merge_quinielas import merge_quinielas
from src.scraper.login import login
from src.utils.config_loader import load_config
from src.utils.data_utils import normalize_date_column
from src.utils.file_utils import safe_read_html, safe_read_csv, safe_save_csv

cfg = load_config(validate_env=False)

# ── Logging ──────────────────────────────────────────────────────────────────
log_level = getattr(logging, cfg.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
log_file = cfg.get("logging", {}).get("file", "logs/app.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── Directorios y rutas ──────────────────────────────────────────────────────
os.makedirs(cfg["data"]["raw_dir"], exist_ok=True)
os.makedirs(cfg["data"]["processed_dir"], exist_ok=True)

HTML_AUX          = cfg["paths"]["html"]["aux"]
HTML_CLAS_AUX     = cfg["paths"]["html"]["clas_aux"]
HTML_MERCADO_AUX  = cfg["paths"]["html"]["mercado"]
HTML_JORNADAS_AUX = cfg["paths"]["html"]["jornadas"]
HTML_SUBIDASBAJADAS = cfg["paths"]["html"]["subidas_bajadas"]
HTML_GAMEWEEK     = cfg["paths"]["html"]["gameweek"]
HTML_QUINIELA     = cfg["paths"]["html"]["quiniela"]
JSON_GW_CALENDAR  = Path(cfg["paths"]["html"]["gameweek_calendar"])
DIR_GAMEWEEKS     = Path(cfg["paths"]["html"]["gameweeks_dir"])

CSV_NOTIFICACIONES  = cfg["paths"]["csv"]["notificaciones"]
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO         = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA         = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS  = cfg["paths"]["csv"]["subidas_bajadas"]
CSV_GAMEWEEK        = cfg["paths"]["csv"]["gameweek"]
CSV_QUINIELA        = cfg["paths"]["csv"]["quiniela"]
CSV_CALENDARIO      = cfg["paths"]["csv"]["calendario"]
CSV_PARTIDOS        = cfg["paths"]["csv"]["partidos"]


def _seleccionar_jornadas_a_descargar(payload_calendario: dict) -> list:
    """Jornadas activas + las 'finished' que aún no tienen partidos y
    clasificación en la BD (backfill automático la primera vez)."""
    partidos = safe_read_csv(CSV_PARTIDOS)
    clasif = safe_read_csv(CSV_CLASIFICACIONES)
    con_partidos = set(partidos["jornada"].dropna().astype(int)) if "jornada" in partidos else set()
    con_clasif = set(clasif["jornada"].dropna().astype(int)) if "jornada" in clasif else set()
    return seleccionar_jornadas(parse_calendario(payload_calendario), con_partidos & con_clasif)


def _leer_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("⚠️ No se pudo leer %s: %s", path, e)
        return None


# ── 0. Scraping ───────────────────────────────────────────────────────────────
# login() lanza excepción si falla críticamente, deteniendo el pipeline.
logger.info("Iniciando proceso de scraping con Playwright...")
try:
    saved_paths = login(seleccionar_jornadas=_seleccionar_jornadas_a_descargar)
    logger.info("✅ Scraping completado. Archivos guardados: %s", list(saved_paths.keys()))
except Exception as e:
    logger.error("❌ El scraping falló: %s", e)
    sys.exit(1)

# Validar que los HTMLs principales existen y no están vacíos
def validate_html(path: str, name: str) -> bool:
    html = safe_read_html(path)
    if html is None:
        logger.warning("⚠️ HTML no disponible para %s (%s)", name, path)
        return False
    if len(html.strip()) < 200:
        logger.warning("⚠️ HTML de %s parece vacío o incompleto (%d chars)", name, len(html.strip()))
        return False
    return True

# Secciones saltadas por HTML no disponible/incompleto. Si al final del
# proceso queda alguna, el script termina con código != 0 para que CI
# marque el job como fallido y dispare el aviso — antes el script siempre
# terminaba con éxito aunque se hubieran saltado secciones enteras.
skipped_sections = []

# ── 1. Notificaciones ─────────────────────────────────────────────────────────
logger.info("Extrayendo notificaciones...")
if not validate_html(HTML_AUX, "notificaciones"):
    logger.warning("⏭️ Saltando notificaciones.")
    skipped_sections.append("notificaciones")
else:
    new_html = safe_read_html(HTML_AUX)
    new_notificaciones = extraer_notificaciones(new_html)
    logger.info("✅ Nuevas notificaciones extraídas.")
    csv_notificaciones = safe_read_csv(CSV_NOTIFICACIONES)
    new_csv_notificaciones = merge_feed_cards_until_match(csv_notificaciones, new_notificaciones)
    safe_save_csv(new_csv_notificaciones, CSV_NOTIFICACIONES)
    logger.info("✅ Notificaciones guardadas.")

# ── 2. Clasificación ──────────────────────────────────────────────────────────
logger.info("Extrayendo clasificaciones...")
if not validate_html(HTML_CLAS_AUX, "clasificaciones"):
    logger.warning("⏭️ Saltando clasificaciones.")
    skipped_sections.append("clasificaciones")
else:
    # Vista por defecto + una clasificación por cada jornada descargada
    # (standings?gw=<id>). Si una jornada sale en ambas, manda la específica.
    frames = [extraer_clasificaciones(safe_read_html(HTML_CLAS_AUX))]
    for path in sorted(DIR_GAMEWEEKS.glob("clasificacion_*.html")):
        frames.append(extraer_clasificaciones(path.read_text(encoding="utf-8")))
    frames = [f for f in frames if not f.empty]
    new_clasificaciones = (
        pd.concat(frames, ignore_index=True).drop_duplicates(["jornada", "nombre"], keep="last")
        if frames else pd.DataFrame()
    )
    logger.info("✅ Nuevas clasificaciones extraídas (jornadas %s).",
                sorted(new_clasificaciones["jornada"].unique()) if not new_clasificaciones.empty else [])
    csv_clasificaciones = safe_read_csv(CSV_CLASIFICACIONES)
    new_csv_clasificacion = merge_clasifications(csv_clasificaciones, new_clasificaciones)
    safe_save_csv(new_csv_clasificacion, CSV_CLASIFICACIONES)
    logger.info("✅ Clasificaciones guardadas.")

# ── 3. Mercado ────────────────────────────────────────────────────────────────
# Deduplicamos por todas las columnas para evitar duplicados si el script
# se ejecuta varias veces el mismo día.
logger.info("Extrayendo mercado...")
if not validate_html(HTML_MERCADO_AUX, "mercado"):
    logger.warning("⏭️ Saltando mercado.")
    skipped_sections.append("mercado")
else:
    html_mercado = safe_read_html(HTML_MERCADO_AUX)
    new_csv_mercado = extraer_mercado(html_mercado)
    logger.info("✅ Nuevos datos de mercado extraídos.")
    csv_mercado = safe_read_csv(CSV_MERCADO)
    csv_mercado = normalize_date_column(csv_mercado, "date")
    new_csv_mercado = normalize_date_column(new_csv_mercado, "date")
    merged_csv_mercado = (
        pd.concat([csv_mercado, new_csv_mercado], ignore_index=True)
        .drop_duplicates()
        .reset_index(drop=True)
    )
    safe_save_csv(merged_csv_mercado, CSV_MERCADO)
    logger.info("✅ Mercado actualizado (%d filas).", len(merged_csv_mercado))

# ── 4. Jornadas ───────────────────────────────────────────────────────────────
logger.info("Extrayendo jornadas...")
if not validate_html(HTML_JORNADAS_AUX, "jornadas"):
    logger.warning("⏭️ Saltando jornadas.")
    skipped_sections.append("jornadas")
else:
    html_jornadas = safe_read_html(HTML_JORNADAS_AUX)
    new_csv_jornadas = extraer_jornadas(html_jornadas)
    logger.info("✅ Nuevas jornadas extraídas.")
    csv_jornadas = safe_read_csv(CSV_JORNADA)
    csv_jornadas = normalize_date_column(csv_jornadas, "date")
    new_csv_jornadas = normalize_date_column(new_csv_jornadas, "date")
    merged_csv_jornadas = (
        pd.concat([csv_jornadas, new_csv_jornadas], ignore_index=True)
        .drop_duplicates(subset=["date", "jornada"])
        .reset_index(drop=True)
    )
    safe_save_csv(merged_csv_jornadas, CSV_JORNADA)
    logger.info("✅ Jornadas actualizadas (%d filas).", len(merged_csv_jornadas))

# ── 5. Subidas y bajadas ──────────────────────────────────────────────────────
logger.info("Extrayendo subidas y bajadas...")
if not validate_html(HTML_SUBIDASBAJADAS, "subidas_bajadas"):
    logger.warning("⏭️ Saltando subidas/bajadas.")
    skipped_sections.append("subidas_bajadas")
else:
    html_subidas_bajadas = safe_read_html(HTML_SUBIDASBAJADAS)
    new_csv_subidas_bajadas = extraer_subidas_bajadas(html_subidas_bajadas)
    logger.info("✅ Nuevas subidas/bajadas extraídas.")
    csv_subidas_bajadas = safe_read_csv(CSV_SUBIDASBAJADAS)
    csv_subidas_bajadas = normalize_date_column(csv_subidas_bajadas, "date")
    new_csv_subidas_bajadas = normalize_date_column(new_csv_subidas_bajadas, "date")
    merged_csv_subidas_bajadas = (
        pd.concat([csv_subidas_bajadas, new_csv_subidas_bajadas], ignore_index=True)
        .drop_duplicates()
        .reset_index(drop=True)
    )
    safe_save_csv(merged_csv_subidas_bajadas, CSV_SUBIDASBAJADAS)
    logger.info("✅ Subidas/bajadas actualizadas (%d filas).", len(merged_csv_subidas_bajadas))

# ── 6. Gameweek ───────────────────────────────────────────────────────────────
logger.info("Extrayendo gameweek...")
if not validate_html(HTML_GAMEWEEK, "gameweek"):
    logger.warning("⏭️ Saltando gameweek.")
    skipped_sections.append("gameweek")
else:
    # Calendario completo de la temporada (estado y fechas de cada jornada).
    payload_calendario = _leer_json(JSON_GW_CALENDAR) if JSON_GW_CALENDAR.exists() else None
    calendario = parse_calendario(payload_calendario) if payload_calendario else pd.DataFrame()
    if not calendario.empty:
        safe_save_csv(calendario, CSV_CALENDARIO)
        logger.info("✅ Calendario guardado (%d jornadas).", len(calendario))
    else:
        logger.warning("⚠️ Sin calendario de jornadas; se usará solo la vista por defecto.")

    # Partidos + gameweek de cada jornada descargada. Los partidos de una
    # jornada solo se guardan si su HTML también se extrajo, para que la
    # jornada no se dé por "descargada" sin sus datos de jugadores.
    frames_gw = [extraer_gameweek(safe_read_html(HTML_GAMEWEEK))]
    nuevos_partidos = []
    for path in sorted(DIR_GAMEWEEKS.glob("gameweek_*.html")):
        df_gw = extraer_gameweek(path.read_text(encoding="utf-8"))
        payload = _leer_json(path.with_suffix(".json"))
        if payload is not None:
            df_p = parse_partidos(payload)
            if not df_gw.empty or not (df_p["estado"] == "played").any():
                nuevos_partidos.append(df_p)
            else:
                logger.warning("⚠️ %s: hay partidos jugados pero 0 filas de jugadores; no se marca como descargada.",
                               path.name)
        if not df_gw.empty:
            frames_gw.append(df_gw)
    frames_gw = [f for f in frames_gw if not f.empty]
    new_gameweek = (
        pd.concat(frames_gw, ignore_index=True)
        .drop_duplicates(["Jornada", "EquipoLocal", "EquipoVisitante", "Manager", "NombreJugador"], keep="last")
        if frames_gw else pd.DataFrame()
    )

    partidos = safe_read_csv(CSV_PARTIDOS)
    if nuevos_partidos:
        partidos = merge_partidos(partidos, pd.concat(nuevos_partidos, ignore_index=True))
        safe_save_csv(partidos, CSV_PARTIDOS)
        logger.info("✅ Partidos guardados (%d en total).", len(partidos))

    # Date = fecha real del partido (antes: día del scrape).
    new_gameweek = anotar_fecha_partido(new_gameweek, partidos)
    logger.info("✅ Nuevas gameweeks extraídas (%d filas, jornadas %s).", len(new_gameweek),
                sorted(new_gameweek["Jornada"].unique()) if not new_gameweek.empty else [])
    csv_gameweek = safe_read_csv(CSV_GAMEWEEK)
    new_csv_gameweek = merge_gameweek(csv_gameweek, new_gameweek)
    safe_save_csv(new_csv_gameweek, CSV_GAMEWEEK)
    logger.info("✅ Gameweek guardado.")

# ── 7. Quiniela ───────────────────────────────────────────────────────────────
# FIX: usaba new_html_clas en lugar de new_html_quin para la validación.
logger.info("Extrayendo quiniela...")
if not validate_html(HTML_QUINIELA, "quiniela"):
    logger.warning("⏭️ Saltando quinielas.")
    skipped_sections.append("quiniela")
else:
    new_html_quin = safe_read_html(HTML_QUINIELA)
    new_quinielas = extraer_quinielas(new_html_quin)
    logger.info("✅ Nuevas quinielas extraídas.")
    csv_quinielas = safe_read_csv(CSV_QUINIELA)
    new_csv_quinielas = merge_quinielas(csv_quinielas, new_quinielas)
    safe_save_csv(new_csv_quinielas, CSV_QUINIELA)
    logger.info("✅ Quinielas guardadas.")

if skipped_sections:
    logger.error(
        "🛑 Proceso de extracción completado con %d sección(es) saltada(s): %s",
        len(skipped_sections), ", ".join(skipped_sections),
    )
    sys.exit(1)

logger.info("🏁 Proceso de extracción completado sin errores.")
