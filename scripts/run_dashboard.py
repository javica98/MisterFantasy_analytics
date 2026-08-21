import logging
import os
import sys
from pathlib import Path


# ── Ajuste de entorno ─────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.visualization.dashboard_por_manager import dashboard_por_manager

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

# Archivos CSV
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS = cfg["paths"]["csv"]["subidas_bajadas"]

# Archivos CSV CLEAN
CSV_NOTIFICACIONES_CLEAN = cfg["paths"]["csv"]["notificaciones_clean"]
CSV_NOTIFICACIONES_JUGADOR = cfg["paths"]["csv"]["notificaciones_jugador"]
CSV_NOTIFICACIONES_CLAUSULA_ACUERDO = cfg["paths"]["csv"]["clausulas_acuerdos"]

logger.info("Creando Dashboard")
csv_notificaciones_clean = safe_read_csv(CSV_NOTIFICACIONES_CLEAN)
csv_clasificaciones = safe_read_csv(CSV_CLASIFICACIONES)
csv_jugadores = safe_read_csv(CSV_NOTIFICACIONES_JUGADOR)
csv_clausulas = safe_read_csv(CSV_NOTIFICACIONES_CLAUSULA_ACUERDO)

if (csv_notificaciones_clean is None) or (csv_clasificaciones is None):
    logger.warning("⏭️ Saltando sección de notificaciones y clasificaciones (no hay CSV disponible).")
else:
    app = dashboard_por_manager(csv_notificaciones_clean,csv_clasificaciones,csv_jugadores,csv_clausulas)
    app.run(debug=False, port=8050)
    logger.info("✅ Dashboard creado")

