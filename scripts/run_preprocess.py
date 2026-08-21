import logging
import os
import sys
from pathlib import Path


# ── Ajuste de entorno ─────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.preprocessing.process_ganancias import procesar_ganancias
from src.preprocessing.process_ganancias_jugador import procesar_ganancias_jugador
from src.preprocessing.process_clausulas_acuerdos import procesar_clausulas_acuerdos

# --- Cargar configuración ---
from src.utils.config_loader import load_config
from src.utils.file_utils import safe_read_csv, safe_save_csv


cfg = load_config(validate_env=False)

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
CSV_NOTIFICACIONES = cfg["paths"]["csv"]["notificaciones"]
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS = cfg["paths"]["csv"]["subidas_bajadas"]

# Archivos CSV
CSV_NOTIFICACIONES_CLEAN = cfg["paths"]["csv"]["notificaciones_clean"]
CSV_NOTIFICACIONES_JUGADOR = cfg["paths"]["csv"]["notificaciones_jugador"]
CSV_NOTIFICACIONES_CLAUSULA_ACUERDO = cfg["paths"]["csv"]["clausulas_acuerdos"]
# --- 1. CLEAN ---
logger.info("Limpiando y estandarizando ganancias...")
csv_notificaciones = safe_read_csv(CSV_NOTIFICACIONES)
if csv_notificaciones.empty:
    logger.warning("⏭️ Saltando limpieza de ganancias (sin datos disponibles).")
else:
    csv_notificaciones_clean = procesar_ganancias(csv_notificaciones)
    safe_save_csv(csv_notificaciones_clean, CSV_NOTIFICACIONES_CLEAN)
    logger.info("✅ Ganancias limpias guardadas en %s (%d filas).", CSV_NOTIFICACIONES_CLEAN, len(csv_notificaciones_clean))

# --- 2. JUGADOR ---
logger.info("Calculando ganancias netas por jugador (Diff compra/venta)...")
csv_notificaciones_clean = safe_read_csv(CSV_NOTIFICACIONES_CLEAN)
if csv_notificaciones_clean.empty:
    logger.warning("⏭️ Saltando cálculo por jugador (sin datos de ganancias limpias disponibles).")
else:
    csv_jugador = procesar_ganancias_jugador(csv_notificaciones_clean)
    safe_save_csv(csv_jugador, CSV_NOTIFICACIONES_JUGADOR)
    logger.info("✅ Ganancias por jugador guardadas en %s (%d filas).", CSV_NOTIFICACIONES_JUGADOR, len(csv_jugador))

# --- 3. CLAUSULAS ---
logger.info("Extrayendo cláusulas y acuerdos...")
csv_notificaciones = safe_read_csv(CSV_NOTIFICACIONES)
if csv_notificaciones.empty:
    logger.warning("⏭️ Saltando extracción de cláusulas (sin datos disponibles).")
else:
    csv_clausulas = procesar_clausulas_acuerdos(csv_notificaciones)
    safe_save_csv(csv_clausulas, CSV_NOTIFICACIONES_CLAUSULA_ACUERDO)
    logger.info("✅ Cláusulas y acuerdos guardados en %s (%d filas).", CSV_NOTIFICACIONES_CLAUSULA_ACUERDO, len(csv_clausulas))


