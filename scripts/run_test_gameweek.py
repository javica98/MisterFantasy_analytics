import os
import sys
import logging
from pathlib import Path


# --- Ajuste del entorno de ejecución ---
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.data.extract_gameweek import extraer_gameweek
from src.data.merge_gameweek import merge_gameweek


# --- Cargar configuración ---
from src.utils.config_loader import load_config
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
HTML_AUX = cfg["paths"]["html"]["aux"]
HTML_CLAS_AUX = cfg["paths"]["html"]["clas_aux"]
HTML_MERCADO_AUX = cfg["paths"]["html"]["mercado"]
HTML_JORNADAS_AUX = cfg["paths"]["html"]["jornadas"]
HTML_SUBIDASBAJADAS = cfg["paths"]["html"]["subidas_bajadas"]
HTML_GAMEWEEK = cfg["paths"]["html"]["gameweek"]
HTML_QUINIELA = cfg["paths"]["html"]["quiniela"]

# Archivos CSV
CSV_NOTIFICACIONES = cfg["paths"]["csv"]["notificaciones"]
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS = cfg["paths"]["csv"]["subidas_bajadas"]
CSV_GAMEWEEK = cfg["paths"]["csv"]["gameweek"]
CSV_QUINIELA = cfg["paths"]["csv"]["quiniela"]

# Variables de entorno (login)
MISTER_USERNAME = cfg["env"]["MISTER_USERNAME"]
MISTER_PASSWORD = cfg["env"]["MISTER_PASSWORD"]
MISTER_BASE_URL = cfg["env"]["MISTER_BASE_URL"]


# --- 6. Gameweek ---
logger.info("Extrayendo gameweek...")
new_html_gameweek = safe_read_html(HTML_GAMEWEEK)
if new_html_gameweek is None:
    logger.warning("⏭️ Saltando sección de Gameweek (no hay HTML disponible).")
else:
    new_gameweek = extraer_gameweek(new_html_gameweek)
    logger.info("✅ Nuevas gameweeks extraídas.")
    csv_gameweek = safe_read_csv(CSV_GAMEWEEK)
    new_csv_gameweek = merge_gameweek(csv_gameweek, new_gameweek)
    safe_save_csv(new_csv_gameweek, CSV_GAMEWEEK)
    logger.info("✅ Nuevas gameweeks añadidas y guardadas.")


logger.info("🏁 Proceso de extracción completado sin errores.")
