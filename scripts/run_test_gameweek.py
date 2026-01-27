import sys
import pandas as pd
import logging

from pathlib import Path
import os, sys

# --- 🔧 Ajuste de ruta raíz del proyecto ---
import sys
import os
from pathlib import Path

# --- 🔧 Ajuste del entorno de ejecución ---
# Detectar raíz del proyecto automáticamente
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent  # sube desde /scripts hasta la raíz
SRC_DIR = ROOT_DIR / "src"

# Asegurar que la raíz y src están en el sys.path
for p in (ROOT_DIR, SRC_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Cambiar el directorio de trabajo a la raíz del proyecto
os.chdir(ROOT_DIR)

print("📂 Directorio raíz:", ROOT_DIR)
print("📁 SRC añadido:", SRC_DIR)
print("📁 sys.path[0]:", sys.path[0])

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
