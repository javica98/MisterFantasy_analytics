import os
import sys
import logging
from datetime import datetime
from pathlib import Path


# --- Ajuste del entorno de ejecución ---
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)



# --- Cargar configuración ---
from src.utils.config_loader import load_config
from src.utils.file_utils import safe_save_png,safe_read_json

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


article_final_path = os.path.join(JSON_NEWS, "news_article.txt")
json_final_path = os.path.join(JSON_NEWS, "news_json.json")



json= safe_read_json(json_final_path)
clasificacion_json= json["clasificacion"]
quiniela_json= json["quinielas"]
cards_json_path = os.path.join(JSON_NEWS, "cards", "news_cards.json")
cards = safe_read_json(cards_json_path)
portada_fichajes = create_pdf("Fichajes",cards,quiniela_json,NEWS_UTILS,IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
portada_jornada = create_pdf("Jornada",cards,clasificacion_json,NEWS_UTILS,IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
fecha_hoy = datetime.today().strftime("%Y-%m-%d")
portada_fichajes_path = os.path.join(IMG_NEWS, f"{fecha_hoy}_fichajes_news.png")
portada_jornada_path = os.path.join(IMG_NEWS, f"{fecha_hoy}_jornada_news.png")
card_save = safe_save_png(portada_fichajes,portada_fichajes_path)
card_save = safe_save_png(portada_jornada,portada_jornada_path)
logger.info("🏁 Proceso de extracción completado sin errores.")


