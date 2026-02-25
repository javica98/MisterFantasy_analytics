from datetime import datetime
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

from src.scraper.login import login

# --- Cargar configuración ---
from src.utils.config_loader import load_config
from src.utils.data_utils import normalize_date_column
from src.utils.file_utils import safe_read_html, safe_read_csv, safe_save_csv,safe_save_png,safe_read_json,safe_save_json,safe_read_text

from src.AI_newspaper.generate_json import generate_json
from src.AI_newspaper.generate_prompt import generate_prompts,build_final_prompt
from src.AI_newspaper.generate_article import generate_articles,parse_generated_text
from src.AI_newspaper.generate_pdf_copy  import create_pdf

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

# Archivos CSV
CSV_NOTIFICACIONES = cfg["paths"]["csv"]["notificaciones"]
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS = cfg["paths"]["csv"]["subidas_bajadas"]
CSV_GAMEWEEK = cfg["paths"]["csv"]["gameweek"]

# Variables de entorno (login)
MISTER_USERNAME = cfg["env"]["MISTER_USERNAME"]
MISTER_PASSWORD = cfg["env"]["MISTER_PASSWORD"]
MISTER_BASE_URL = cfg["env"]["MISTER_BASE_URL"]

JSON_NEWS = cfg["paths"]["json"]["news"]
IMG_NEWS = cfg["paths"]["images"]["news"]
#PHOTOS
IMAGES_TEAMS_DIR = cfg["paths"]["images"]["teams_dir"]
DEFAULT_TEAM_IMAGE = cfg["paths"]["images"]["default_team"]
NEWS_UTILS = cfg["paths"]["images"]["news_utils"]


article_final_path = os.path.join(JSON_NEWS, f"news_article.txt")
json_final_path = os.path.join(JSON_NEWS, f"news_json.json")



json= safe_read_json(json_final_path)
clasificacion_json= json["clasificacion"]
quiniela_json= json["quinielas"]
cards_json_path = os.path.join(JSON_NEWS, f"news_cards.json")
cards = safe_read_json(cards_json_path)
portada_fichajes = create_pdf("Fichajes",cards,quiniela_json,NEWS_UTILS,IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
portada_jornada = create_pdf("Jornada",cards,clasificacion_json,NEWS_UTILS,IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
fecha_hoy = datetime.today().strftime("%Y-%m-%d")
portada_fichajes_path = os.path.join(IMG_NEWS, f"{fecha_hoy}_fichajes_news.png")
portada_jornada_path = os.path.join(IMG_NEWS, f"{fecha_hoy}_jornada_news.png")
card_save = safe_save_png(portada_fichajes,portada_fichajes_path)
card_save = safe_save_png(portada_jornada,portada_jornada_path)
logger.info("🏁 Proceso de extracción completado sin errores.")


