import os
import sys
import logging
from pathlib import Path


# --- Ajuste del entorno de ejecución ---
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.visualization.monthly_dashboard import monthly_dashboard
from src.visualization.create_pdfs import create_report


# --- Cargar configuración ---
from src.utils.config_loader import load_config
from src.utils.file_utils import safe_read_csv


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
os.makedirs(cfg["data"]["processed_dir"], exist_ok=True)

# Directorios base
DATA_PROCESSED = cfg["data"]["processed_dir"]

#PHOTOS
IMAGES_TEAMS_DIR = cfg["paths"]["images"]["teams_dir"]
DEFAULT_TEAM_IMAGE = cfg["paths"]["images"]["default_team"]

# Archivos CSV
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS = cfg["paths"]["csv"]["subidas_bajadas"]

# Archivos CSV CLEAN
CSV_NOTIFICACIONES_CLEAN = cfg["paths"]["csv"]["notificaciones_clean"]
CSV_NOTIFICACIONES_JUGADOR = cfg["paths"]["csv"]["notificaciones_jugador"]
CSV_NOTIFICACIONES_CLAUSULA_ACUERDO = cfg["paths"]["csv"]["clausulas_acuerdos"]

#Archivos pdfs
PDF_MONTHLY_TEMPLATE = cfg["paths"]["pdf"]["template"]
PDF_MONTHLY_REPORTS = cfg["paths"]["pdf"]["reports"]

logger.info("Creando Dashboard Mensual")
csv_jornadas = safe_read_csv(CSV_JORNADA)
csv_notificaciones_clean = safe_read_csv(CSV_NOTIFICACIONES_CLEAN)
csv_clasificaciones = safe_read_csv(CSV_CLASIFICACIONES)
csv_jugadores = safe_read_csv(CSV_NOTIFICACIONES_JUGADOR)
csv_clausulas = safe_read_csv(CSV_NOTIFICACIONES_CLAUSULA_ACUERDO)

if csv_notificaciones_clean.empty or csv_clasificaciones.empty:
    logger.warning("⏭️ Saltando sección de notificaciones y clasificaciones (sin datos disponibles).")
else:
    figures = monthly_dashboard(csv_jornadas,csv_clasificaciones,csv_notificaciones_clean,csv_jugadores,csv_clausulas)
    logger.info("✅ Figuras creadas")
    pdf = create_report(PDF_MONTHLY_TEMPLATE,PDF_MONTHLY_REPORTS,figures[0],figures[1],figures[2],figures[3],figures[4],figures[5],figures[6],IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
    logger.info("✅ Dashboard Mensual creado")


