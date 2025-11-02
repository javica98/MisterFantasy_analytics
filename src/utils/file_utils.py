import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def safe_read_html(path: str):
    """Lee un archivo HTML si existe; de lo contrario, devuelve None."""
    if not os.path.exists(path):
        logger.warning(f"No se encontró el HTML: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error al leer HTML {path}: {e}")
        return None


def safe_read_csv(path: str):
    """Lee un CSV si existe; de lo contrario, devuelve un DataFrame vacío."""
    if not os.path.exists(path):
        logger.warning(f"CSV no encontrado, creando vacío: {path}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as e:
        logger.error(f"Error al leer CSV {path}: {e}")
        return pd.DataFrame()


def safe_save_csv(df: pd.DataFrame, path: str):
    """Guarda un DataFrame en CSV de forma segura."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df.to_csv(path, index=False)
        logger.info(f"💾 Guardado CSV: {path}")
    except Exception as e:
        logger.error(f"Error al guardar CSV {path}: {e}")
