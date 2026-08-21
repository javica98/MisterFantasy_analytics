import os
import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd

# --- Ajuste del entorno de ejecución ---
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.data.process_modeling import procesar_model_data

# --- Cargar configuración ---
from src.utils.config_loader import load_config
from src.utils.file_utils import safe_read_csv, safe_save_csv

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

logger.debug("Directorio raíz: %s", ROOT_DIR)

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
CSV_DATA_MODEL = cfg["paths"]["csv"]["model"]

# Results audit
CSV_AUDIT = cfg["paths"]["results"]["data_audit"]


logger.info("Creando Dashboard")
csv_notificaciones_clean = safe_read_csv(CSV_NOTIFICACIONES_CLEAN)
csv_mercado = safe_read_csv(CSV_MERCADO)
csv_subidasBajadas = safe_read_csv(CSV_SUBIDASBAJADAS)
csv_jornada = safe_read_csv(CSV_JORNADA)

if csv_notificaciones_clean.empty or csv_mercado.empty:
    logger.warning("⏭️ Saltando sección de notificaciones y clasificaciones (sin datos disponibles).")
else:
    newData = procesar_model_data(csv_mercado, csv_subidasBajadas, csv_jornada, csv_notificaciones_clean)
    safe_save_csv(newData, CSV_DATA_MODEL)
    logger.info("✅ Model data creado")


# Carga tu base de datos
df = safe_read_csv(CSV_DATA_MODEL)

# =========================
# PASO 1: DIMENSIONES Y TIPOS
# =========================
logger.info("Dimensiones del dataset: %s", df.shape)
logger.info("Tipos de datos:\n%s", df.dtypes)

# =========================
# PASO 2: DUPLICADOS
# =========================
duplicados_exactos = df.duplicated().sum()
logger.info("Duplicados exactos encontrados: %d", duplicados_exactos)

# Duplicados lógicos (ajusta columnas clave según tu dataset)
keys_logicas = ['date', 'jugador']
duplicados_logicos = df.duplicated(subset=keys_logicas).sum()
logger.info("Duplicados lógicos por keys %s: %d", keys_logicas, duplicados_logicos)

# =========================
# PASO 3: NULOS
# =========================
nulos = df.isnull().sum()
pct_nulos = (nulos / len(df)) * 100
nulos_df = pd.DataFrame({'nulos': nulos, 'pct_nulos': pct_nulos})
logger.info("Valores nulos por columna:\n%s", nulos_df)

# =========================
# PASO 4: ESTADÍSTICAS BÁSICAS
# =========================
logger.info("Estadísticas numéricas:\n%s", df.describe())

# Variables categóricas
cat_cols = df.select_dtypes(include=['object', 'category']).columns
for col in cat_cols:
    logger.info("Column: %s\n%s", col, df[col].value_counts())

# =========================
# PASO 5: CONSISTENCIA DE CLAVES
# =========================
for key in ['date', 'jugador']:
    logger.info("Unique %s: %d | Total rows: %d", key, df[key].nunique(), len(df))

# =========================
# PASO 6: OUTLIERS SIMPLES
# =========================
num_cols = df.select_dtypes(include=np.number).columns
outliers_summary = {}
for col in num_cols:
    Q1 = df[col].quantile(0.25)
    Q3 = df[col].quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5*IQR
    upper = Q3 + 1.5*IQR
    outliers = df[(df[col] < lower) | (df[col] > upper)]
    outliers_summary[col] = len(outliers)
logger.info("Outliers detectados por columna:\n%s", outliers_summary)

# =========================
# PASO 7: RESUMEN DE AUDITORÍA
# =========================
audit_df = pd.DataFrame({
    'columna': df.columns,
    'tipo': df.dtypes,
    'nulos': df.isnull().sum(),
    'pct_nulos': (df.isnull().sum()/len(df))*100,
    'valores_unicos': df.nunique(),
    'duplicados_logicos': df.duplicated(subset=keys_logicas).sum(),
})

logger.info("Resumen de auditoría:\n%s", audit_df)

safe_save_csv(audit_df, CSV_AUDIT)
