import os
import yaml
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def load_config():
    """
    Carga las configuraciones desde .env y config.yaml, combinadas en un solo dict.
    """
    # Base del proyecto (3 niveles arriba del archivo actual)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    dotenv_path = os.path.join(base_dir, "config", ".env")
    load_dotenv(dotenv_path)

    # Carga config.yaml
    config_path = os.path.join(base_dir, "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Añade variables de entorno cargadas desde .env
    cfg["env"] = {
        "MISTER_USERNAME": os.getenv("MISTER_USERNAME"),
        "MISTER_PASSWORD": os.getenv("MISTER_PASSWORD"),
        "MISTER_BASE_URL": os.getenv("MISTER_BASE_URL", "https://mister.mundodeportivo.com"),
    }

    return cfg


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("Cargando configuración...")

    cfg = load_config()
    logger.info("✅ CONFIG LOAD OK")
    logger.info(cfg)
