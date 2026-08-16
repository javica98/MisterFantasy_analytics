import sys
import os
import logging
from pathlib import Path

import pandas as pd

# ── Ajuste de rutas ──────────────────────────────────────────────────────────
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent
SRC_DIR = ROOT_DIR / "src"

for p in (ROOT_DIR, SRC_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.chdir(ROOT_DIR)

from src.data.merge_notifications import merge_feed_cards_until_match
from src.data.merge_clasification import merge_clasifications
from src.data.extract_notificaciones import extraer_notificaciones
from src.data.extract_clasificacion import extraer_clasificaciones
from src.data.extract_mercado import extraer_mercado
from src.data.extract_jornadas import extraer_jornadas
from src.data.extract_subidas_bajadas import extraer_subidas_bajadas
from src.data.extract_gameweek import extraer_gameweek
from src.data.merge_gameweek import merge_gameweek
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

CSV_NOTIFICACIONES  = cfg["paths"]["csv"]["notificaciones"]
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO         = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA         = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS  = cfg["paths"]["csv"]["subidas_bajadas"]
CSV_GAMEWEEK        = cfg["paths"]["csv"]["gameweek"]
CSV_QUINIELA        = cfg["paths"]["csv"]["quiniela"]

# ── 0. Scraping ───────────────────────────────────────────────────────────────
# login() lanza excepción si falla críticamente, deteniendo el pipeline.
logger.info("Iniciando proceso de scraping con Playwright...")
try:
    saved_paths = login()
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

# ── 1. Notificaciones ─────────────────────────────────────────────────────────
logger.info("Extrayendo notificaciones...")
if not validate_html(HTML_AUX, "notificaciones"):
    logger.warning("⏭️ Saltando notificaciones.")
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
else:
    new_html_clas = safe_read_html(HTML_CLAS_AUX)
    new_clasificaciones = extraer_clasificaciones(new_html_clas)
    logger.info("✅ Nuevas clasificaciones extraídas.")
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
else:
    new_html_gameweek = safe_read_html(HTML_GAMEWEEK)
    new_gameweek = extraer_gameweek(new_html_gameweek)
    logger.info("✅ Nuevas gameweeks extraídas.")
    csv_gameweek = safe_read_csv(CSV_GAMEWEEK)
    new_csv_gameweek = merge_gameweek(csv_gameweek, new_gameweek)
    safe_save_csv(new_csv_gameweek, CSV_GAMEWEEK)
    logger.info("✅ Gameweek guardado.")

# ── 7. Quiniela ───────────────────────────────────────────────────────────────
# FIX: usaba new_html_clas en lugar de new_html_quin para la validación.
logger.info("Extrayendo quiniela...")
if not validate_html(HTML_QUINIELA, "quiniela"):
    logger.warning("⏭️ Saltando quinielas.")
else:
    new_html_quin = safe_read_html(HTML_QUINIELA)
    new_quinielas = extraer_quinielas(new_html_quin)
    logger.info("✅ Nuevas quinielas extraídas.")
    csv_quinielas = safe_read_csv(CSV_QUINIELA)
    new_csv_quinielas = merge_quinielas(csv_quinielas, new_quinielas)
    safe_save_csv(new_csv_quinielas, CSV_QUINIELA)
    logger.info("✅ Quinielas guardadas.")

logger.info("🏁 Proceso de extracción completado sin errores.")
