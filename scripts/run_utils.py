from datetime import datetime
import sys
import logging

from pathlib import Path
import os, sys

# --- ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒâ€šÃ‚Â§ Ajuste de ruta raÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­z del proyecto ---
import sys
import os
from pathlib import Path

# --- ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒâ€šÃ‚Â§ Ajuste del entorno de ejecuciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n ---
# Detectar raÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­z del proyecto automÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¡ticamente
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent  # sube desde /scripts hasta la raÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­z
SRC_DIR = ROOT_DIR / "src"

# Asegurar que la raÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­z y src estÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¡n en el sys.path
for p in (ROOT_DIR, SRC_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Cambiar el directorio de trabajo a la raÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â­z del proyecto
os.chdir(ROOT_DIR)

print("Project root:", ROOT_DIR)
print("SRC added:", SRC_DIR)
print("sys.path[0]:", sys.path[0])

from src.utils.photo_utils import remove_background_image

def test_remove_background_photos() -> None:
    photos_dir = Path(r"C:\Users\javier.carbonell\.vscode\Proyects\MisterFantasy_analytics\newspaper\photos")
    input_dir = photos_dir / "with_bg"
    output_dir = photos_dir / "no_bg"
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_ext = {".png", ".jpg", ".jpeg", ".webp"}
    images = [p for p in photos_dir.iterdir() if p.is_file() and p.suffix.lower() in valid_ext]

    if not images:
        print("No se han encontrado imÃƒÆ’Ã‚Â¡genes para procesar en:", photos_dir)
        return

    print(f"Procesando {len(images)} imÃƒÆ’Ã‚Â¡genes en {photos_dir}")
    for image_path in images:
        out_name = f"{image_path.stem}_no_bg.png"
        out_path = output_dir / out_name
        try:
            remove_background_image(str(image_path), str(out_path))
            print("OK:", out_path)
        except Exception as exc:
            print("ERROR:", image_path, "-", exc)


if os.getenv("RUN_BG_TEST", "0") == "1":
    test_remove_background_photos()
    sys.exit(0)

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

# --- Cargar configuraciÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â³n ---
from src.utils.config_loader import load_config
from src.utils.data_utils import normalize_date_column
from src.utils.file_utils import safe_read_html, safe_read_csv, safe_save_csv,safe_save_png,safe_read_json,safe_save_json,safe_read_text

from src.AI_newspaper.generate_json import generate_json
from src.AI_newspaper.generate_prompt import generate_prompts,build_final_prompt
from src.AI_newspaper.generate_article import generate_articles
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




