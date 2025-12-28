import sys
import pandas as pd
import logging
import numpy as np

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

from src.data.process_modeling import procesar_model_data

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

if (csv_notificaciones_clean is None) or (csv_mercado is None):
    logger.warning("⏭️ Saltando sección de notificaciones y clasificaciones (no hay CSV disponible).")
else:
    newData = procesar_model_data(csv_mercado,csv_subidasBajadas,csv_jornada,csv_notificaciones_clean)
    safe_save_csv(newData,CSV_DATA_MODEL)
    logger.info("✅ Model data creado")


# Carga tu base de datos
df =  safe_read_csv(CSV_DATA_MODEL)

# =========================
# PASO 1: DIMENSIONES Y TIPOS
# =========================
print("Dimensiones del dataset:", df.shape)
print("\nTipos de datos:")
print(df.dtypes)

# =========================
# PASO 2: DUPLICADOS
# =========================
duplicados_exactos = df.duplicated().sum()
print(f"\nDuplicados exactos encontrados: {duplicados_exactos}")

# Duplicados lógicos (ajusta columnas clave según tu dataset)
keys_logicas = ['date', 'jugador']
duplicados_logicos = df.duplicated(subset=keys_logicas).sum()
print(f"Duplicados lógicos por keys {keys_logicas}: {duplicados_logicos}")

# =========================
# PASO 3: NULOS
# =========================
nulos = df.isnull().sum()
pct_nulos = (nulos / len(df)) * 100
nulos_df = pd.DataFrame({'nulos': nulos, 'pct_nulos': pct_nulos})
print("\nValores nulos por columna:")
print(nulos_df)

# =========================
# PASO 4: ESTADÍSTICAS BÁSICAS
# =========================
print("\nEstadísticas numéricas:")
print(df.describe())

# Variables categóricas
cat_cols = df.select_dtypes(include=['object', 'category']).columns
for col in cat_cols:
    print(f"\nColumn: {col}")
    print(df[col].value_counts())

# =========================
# PASO 5: CONSISTENCIA DE CLAVES
# =========================
for key in ['date', 'jugador']:
    print(f"\nUnique {key}: {df[key].nunique()} | Total rows: {len(df)}")

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
print("\nOutliers detectados por columna:")
print(outliers_summary)

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

print("\nResumen de auditoría:")
print(audit_df)

safe_save_csv(audit_df,CSV_AUDIT)
