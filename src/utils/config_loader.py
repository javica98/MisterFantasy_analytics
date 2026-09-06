import os
import yaml
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Raíz del proyecto: tres niveles arriba de este archivo (src/utils/config_loader.py)
_BASE_DIR = Path(__file__).resolve().parent.parent.parent

REQUIRED_ENV_VARS = ["MISTER_USERNAME", "MISTER_PASSWORD", "GEMINI_API_KEY", "GROQ_API_KEY"]


def get_base_dir() -> Path:
    """Devuelve la raíz absoluta del proyecto como Path."""
    return _BASE_DIR


def resolve_path(cfg: dict, *keys: str) -> Path:
    """
    Navega el dict de config por las keys dadas y devuelve la ruta como
    Path absoluto relativo a la raíz del proyecto.

    Ejemplo: resolve_path(cfg, "paths", "csv", "notificaciones")
    """
    value = cfg
    for key in keys:
        value = value[key]
    return _BASE_DIR / value


def load_config(validate_env: bool = True) -> dict:
    """
    Carga las configuraciones desde .env y config.yaml, combinadas en un solo dict.
    Si validate_env=True lanza EnvironmentError si faltan variables críticas.
    """
    dotenv_path = _BASE_DIR / "config" / ".env"
    load_dotenv(dotenv_path)

    config_path = _BASE_DIR / "config" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["env"] = {
        "MISTER_USERNAME": os.getenv("MISTER_USERNAME"),
        "MISTER_PASSWORD": os.getenv("MISTER_PASSWORD"),
        "MISTER_BASE_URL": os.getenv("MISTER_BASE_URL", "https://mister.mundodeportivo.com"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    }

    if validate_env:
        missing = [v for v in REQUIRED_ENV_VARS if not cfg["env"].get(v)]
        if missing:
            raise EnvironmentError(
                f"Faltan variables de entorno requeridas: {missing}. "
                f"Comprueba config/.env"
            )

    return cfg


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("Cargando configuración...")

    cfg = load_config()
    logger.info("CONFIG LOAD OK")
    logger.info(cfg)
