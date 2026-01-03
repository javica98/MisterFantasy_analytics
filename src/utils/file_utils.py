import json
import os
import pandas as pd
import logging
from PIL import Image

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


def safe_read_json(path: str):
    """
    Lee un JSON si existe; de lo contrario, devuelve un dict vacío.
    Maneja errores de lectura y JSON corrupto.
    """
    if not os.path.exists(path):
        logger.warning(f"JSON no encontrado, creando vacío: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except json.JSONDecodeError as e:
        logger.error(f"JSON corrupto en {path}: {e}")
        return {}

    except Exception as e:
        logger.error(f"Error al leer JSON {path}: {e}")
        return {}
    

def safe_save_json(data: dict, path: str):
    """
    Guarda un diccionario en JSON de forma segura.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

        logger.info(f"💾 Guardado JSON: {path}")

    except Exception as e:
        logger.error(f"Error al guardar JSON {path}: {e}")

def safe_read_text(path: str) -> str:
    """
    Lee un archivo de texto si existe; de lo contrario, devuelve cadena vacía.
    Maneja errores de lectura.
    """
    if not os.path.exists(path):
        logger.warning(f"Archivo de texto no encontrado, devolviendo vacío: {path}")
        return ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        logger.error(f"Error al leer archivo de texto {path}: {e}")
        return ""


def safe_save_text(data: str, path: str):
    """
    Guarda un string en un archivo de texto de forma segura.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(data)

        logger.info(f"💾 Guardado archivo de texto: {path}")

    except Exception as e:
        logger.error(f"Error al guardar archivo de texto {path}: {e}")
       

def safe_save_png(image: Image.Image, path: str):
    """
    Guarda una imagen PIL en PNG de forma segura.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)

        image.save(path, format="PNG")
        logger.info(f"🖼️ Guardada imagen PNG: {path}")

    except Exception as e:
        logger.error(f"Error al guardar imagen PNG {path}: {e}")

def safe_read_png(path: str):
    """
    Lee una imagen PNG si existe; si no, devuelve None.
    Maneja errores de lectura.
    """
    if not os.path.exists(path):
        logger.warning(f"Imagen PNG no encontrada: {path}")
        return None

    try:
        return Image.open(path).convert("RGBA")

    except Exception as e:
        logger.error(f"Error al leer imagen PNG {path}: {e}")
        return None
