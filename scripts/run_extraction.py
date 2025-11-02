import os
import sys
import pandas as pd
import logging

# Añadir la carpeta raíz (MisterProyect) al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.merge_notifications import merge_feed_cards_until_match
from src.data.merge_clasification import merge_clasifications
from src.data.extract_notificaciones import extraer_notificaciones
from src.data.extract_clasificacion import extraer_clasificaciones
from src.data.extract_mercado import extraer_mercado
from src.data.extract_jornadas import extraer_jornadas
from src.data.extract_subidas_bajadas import extraer_subidas_bajadas

from src.scraper.login import login

# --- Cargar configuración ---
from src.utils.config_loader import load_config
from src.utils.data_utils import normalize_date_column
from src.utils.file_utils import safe_read_html, safe_read_csv, safe_save_csv


cfg = load_config()

# --- Configurar logging ---
log_level = getattr(logging, cfg.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
log_file = cfg.get("logging", {}).get("file", "logs/app.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Asegurar directorios base ---
os.makedirs(cfg["data"]["raw_dir"], exist_ok=True)
os.makedirs(cfg["data"]["processed_dir"], exist_ok=True)

# Directorios base
DATA_RAW = cfg["data"]["raw_dir"]
DATA_PROCESSED = cfg["data"]["processed_dir"]

# Archivos HTML
HTML_MAIN = cfg["paths"]["html"]["main"]
HTML_AUX = cfg["paths"]["html"]["aux"]
HTML_CLAS_MAIN = cfg["paths"]["html"]["clas_main"]
HTML_CLAS_AUX = cfg["paths"]["html"]["clas_aux"]
HTML_MERCADO_AUX = cfg["paths"]["html"]["mercado"]
HTML_JORNADAS_AUX = cfg["paths"]["html"]["jornadas"]
HTML_SUBIDASBAJADAS = cfg["paths"]["html"]["subidas_bajadas"]

# Archivos CSV
CSV_NOTIFICACIONES = cfg["paths"]["csv"]["notificaciones"]
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS = cfg["paths"]["csv"]["subidas_bajadas"]

# Variables de entorno (login)
MISTER_USERNAME = cfg["env"]["MISTER_USERNAME"]
MISTER_PASSWORD = cfg["env"]["MISTER_PASSWORD"]
MISTER_BASE_URL = cfg["env"]["MISTER_BASE_URL"]

# --- 0. Web Scrapper ---
logger.info("Iniciando proceso de scraping con Playwright...")
login()

# --- 1. Notificaciones ---
logger.info("Extrayendo notificaciones...")
new_html = safe_read_html(HTML_AUX)
if new_html is None:
    logger.warning("⏭️ Saltando sección de notificaciones (no hay HTML disponible).")
else:
    new_notificaciones = extraer_notificaciones(new_html)
    logger.info("✅ Nuevas notificaciones extraídas.")
    csv_notificaciones = safe_read_csv(CSV_NOTIFICACIONES)
    new_csv_notificaciones = merge_feed_cards_until_match(csv_notificaciones, new_notificaciones)
    safe_save_csv(new_csv_notificaciones, CSV_NOTIFICACIONES)
    logger.info("✅ Nuevas notificaciones añadidas y guardadas.")


# --- 2. Clasificación ---
logger.info("Extrayendo clasificaciones...")
new_html_clas = safe_read_html(HTML_CLAS_AUX)
if new_html_clas is None:
    logger.warning("⏭️ Saltando sección de clasificaciones (no hay HTML disponible).")
else:
    new_clasificaciones = extraer_clasificaciones(new_html_clas)
    logger.info("✅ Nuevas clasificaciones extraídas.")
    csv_clasificaciones = safe_read_csv(CSV_CLASIFICACIONES)
    new_csv_clasificacion = merge_clasifications(csv_clasificaciones, new_clasificaciones)
    safe_save_csv(new_csv_clasificacion, CSV_CLASIFICACIONES)
    logger.info("✅ Nuevas clasificaciones añadidas y guardadas.")


# --- 3. Mercado ---
logger.info("Extrayendo mercado...")
html_mercado = safe_read_html(HTML_MERCADO_AUX)
if html_mercado is None:
    logger.warning("⏭️ Saltando sección de mercado (no hay HTML disponible).")
else:
    new_csv_mercado = extraer_mercado(html_mercado)
    logger.info("✅ Nuevos datos de mercado extraídos.")
    csv_mercado = safe_read_csv(CSV_MERCADO)
    csv_mercado = normalize_date_column(csv_mercado, "date")
    new_csv_mercado = normalize_date_column(new_csv_mercado, "date")
    merged_csv_mercado = pd.concat([csv_mercado, new_csv_mercado], ignore_index=True)
    safe_save_csv(merged_csv_mercado, CSV_MERCADO)
    logger.info("✅ Datos de mercado actualizados correctamente.")


# --- 4. Jornada futura ---
logger.info("Extrayendo jornada futura...")
html_jornadas = safe_read_html(HTML_JORNADAS_AUX)
if html_jornadas is None:
    logger.warning("⏭️ Saltando sección de jornadas futuras (no hay HTML disponible).")
else:
    new_csv_jornadas = extraer_jornadas(html_jornadas)
    logger.info("✅ Nuevas jornadas extraídas.")
    csv_jornadas = safe_read_csv(CSV_JORNADA)
    csv_jornadas = normalize_date_column(csv_jornadas, "date")
    new_csv_jornadas = normalize_date_column(new_csv_jornadas, "date")
    merged_csv_jornadas = pd.concat([csv_jornadas, new_csv_jornadas], ignore_index=True)
    safe_save_csv(merged_csv_jornadas, CSV_JORNADA)
    logger.info("✅ Datos de jornadas actualizados correctamente.")


# --- 5. Subidas y bajadas ---
logger.info("Extrayendo subidas y bajadas...")
html_subidas_bajadas = safe_read_html(HTML_SUBIDASBAJADAS)
if html_subidas_bajadas is None:
    logger.warning("⏭️ Saltando sección de subidas y bajadas (no hay HTML disponible).")
else:
    new_csv_subidas_bajadas = extraer_subidas_bajadas(html_subidas_bajadas)
    logger.info("✅ Nuevas subidas/bajadas extraídas.")
    csv_subidas_bajadas = safe_read_csv(CSV_SUBIDASBAJADAS)
    csv_subidas_bajadas = normalize_date_column(csv_subidas_bajadas, "date")
    new_csv_subidas_bajadas = normalize_date_column(new_csv_subidas_bajadas, "date")
    merged_csv_subidas_bajadas = pd.concat([csv_subidas_bajadas, new_csv_subidas_bajadas], ignore_index=True)
    safe_save_csv(merged_csv_subidas_bajadas, CSV_SUBIDASBAJADAS)
    logger.info("✅ Datos de subidas/bajadas actualizados correctamente.")

logger.info("🏁 Proceso de extracción completado sin errores.")
