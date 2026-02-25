from datetime import datetime
import sys
import pandas as pd
import logging

from pydantic import ValidationError
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


from src.AI_newspaper.generate_json import generate_json
from src.AI_newspaper.generate_prompt import generate_prompts,build_final_prompt
from src.AI_newspaper.generate_article import generate_articles
from src.AI_newspaper.generate_pdf import create_pdf



from src.AI_newspaper.SchemeValidator import FinalJSON
# --- Cargar configuración ---
from src.utils.config_loader import load_config
from src.utils.data_utils import normalize_date_column
from src.utils.file_utils import safe_read_html, safe_read_csv,safe_read_json, safe_save_csv,safe_save_json,safe_read_text, safe_save_text,safe_save_png


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
HTML_QUINIELAS = cfg["paths"]["html"]["quiniela"]

# Archivos CSV
CSV_NOTIFICACIONES = cfg["paths"]["csv"]["notificaciones"]
CSV_NOTIFICACIONES_CLEAN = cfg["paths"]["csv"]["notificaciones_clean"]
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS = cfg["paths"]["csv"]["subidas_bajadas"]
CSV_GAMEWEEK = cfg["paths"]["csv"]["gameweek"]
CSV_QUINIELAS = cfg["paths"]["csv"]["quiniela"]

# Archivos CSV
JSON_NEWS = cfg["paths"]["json"]["news"]
NEWS_UTILS = cfg["paths"]["images"]["news_utils"]

#PHOTOS
IMAGES_TEAMS_DIR = cfg["paths"]["images"]["teams_dir"]
DEFAULT_TEAM_IMAGE = cfg["paths"]["images"]["default_team"]
NEWS_UTILS = cfg["paths"]["images"]["news_utils"]
IMG_NEWS = cfg["paths"]["images"]["news"]

# Variables de entorno (login)
MISTER_USERNAME = cfg["env"]["MISTER_USERNAME"]
MISTER_PASSWORD = cfg["env"]["MISTER_PASSWORD"]
MISTER_BASE_URL = cfg["env"]["MISTER_BASE_URL"]
fecha_hoy = datetime.today().strftime("%Y-%m-%d")
# --- 1. Create JSONs ---
logger.info("Creando Jsons...")
csv_gameweek = safe_read_csv(CSV_GAMEWEEK)
csv_notificaciones = safe_read_csv(CSV_NOTIFICACIONES_CLEAN)
csv_clasificacion = safe_read_csv(CSV_CLASIFICACIONES)
csv_quinielas = safe_read_csv(CSV_QUINIELAS)

if (csv_gameweek is None)and (csv_notificaciones is None):
    logger.warning("⏭️ Saltando csvs .csv no existe.")
else:
    daily_json = generate_json(3,csv_notificaciones[csv_notificaciones['type'] == 'transfer'],csv_gameweek,csv_clasificacion,csv_quinielas)
    logger.info("✅ Json creado.")
    json_final_path = os.path.join(JSON_NEWS, f"news_json.json")
    daily_json = safe_save_json(daily_json,json_final_path)
    
# --- 2. Crear prompt ---
logger.info("Creando prompt...")
json_new = safe_read_json(json_final_path)
if (json_new is None):
    logger.warning("⏭️ Saltando prompt .json no existe.")
else:
    prompt_json = generate_prompts(json_new)
    commun_prompt_json = build_final_prompt(prompt_json["bloques"],json_new)
    logger.info("✅ Prompt Json creado.")
    prompt_final_path = os.path.join(JSON_NEWS, f"news_prompt.txt")
    prompt_saved = safe_save_text(commun_prompt_json,prompt_final_path)

# --- 3. Llamar Gemini y crear contenido---
prompt_txt = safe_read_text(prompt_final_path)
for _ in range(3):
    logger.info("📡 Llamando a Gemini para generar los textos...")
    texto_generado = generate_articles(prompt_txt)
    try:
        validated_data = FinalJSON(**texto_generado)
        logger.info("🏁 Proceso de validación de esquema completados.")
        break
    except ValidationError:
        logger.info("JSON inválido, reintentando...")

logger.info("✅ Todo el contenido creado.")
cards_json_path = os.path.join(JSON_NEWS, f"news_cards.json")
json_weekly_path = os.path.join(JSON_NEWS, f"{fecha_hoy}_json.json")
article = safe_save_json(texto_generado,cards_json_path)
article = safe_save_json(texto_generado,json_weekly_path)

#--- 4.Crear Pdf
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