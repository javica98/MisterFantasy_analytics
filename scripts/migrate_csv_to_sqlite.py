"""
migrate_csv_to_sqlite.py
=========================
Migración única: importa los CSVs de temporada a la base de datos SQLite
(data/mister.db), etiquetados con su columna `temporada`.

Fuentes:
  - archive/temporada_2025-26/data/processed/*.csv  -> temporada "2025-26"
  - data/processed/*.csv                            -> temporada activa
                                                        (config.yaml -> season.current)

Se excluye `test.csv` (artefacto de pruebas/desarrollo, no es dato de temporada).

Idempotente: se puede volver a ejecutar sin duplicar filas (cada tabla se
sobreescribe por temporada, no se hace append ciego).

Uso:
    python scripts/migrate_csv_to_sqlite.py
"""

import sys
import logging
from pathlib import Path

import pandas as pd

# ── Entorno ───────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.utils import db as db_utils
from src.utils.config_loader import load_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

EXCLUDED_STEMS = {"test"}


def _import_dir(csv_dir: Path, temporada: str) -> list[tuple[str, str, int]]:
    """Importa todos los CSV de `csv_dir` a la BD bajo `temporada`.

    Devuelve una lista de (tabla, temporada, filas_importadas) para el resumen.
    """
    summary = []
    if not csv_dir.exists():
        logger.warning("Directorio no encontrado, se omite: %s", csv_dir)
        return summary

    for csv_path in sorted(csv_dir.glob("*.csv")):
        table = csv_path.stem
        if table in EXCLUDED_STEMS:
            logger.info("  [%s] %s -> excluido (artefacto de pruebas)", temporada, csv_path.name)
            continue

        try:
            df = pd.read_csv(csv_path)
        except pd.errors.EmptyDataError:
            logger.info("  [%s] %s -> vacío (sin cabecera), 0 filas", temporada, csv_path.name)
            continue

        db_utils.write_table(df, table, temporada)
        summary.append((table, temporada, len(df)))
        logger.info("  [%s] %s -> tabla '%s': %d filas", temporada, csv_path.name, table, len(df))

    return summary


def main():
    cfg = load_config(validate_env=False)
    temporada_actual = cfg["season"]["current"]

    logger.info("Base de datos destino: %s", db_utils.get_db_path())

    logger.info("Importando temporada archivada 2025-26...")
    archive_dir = ROOT_DIR / "archive" / "temporada_2025-26" / "data" / "processed"
    summary = _import_dir(archive_dir, "2025-26")

    logger.info("Importando temporada activa %s...", temporada_actual)
    current_dir = ROOT_DIR / "data" / "processed"
    summary += _import_dir(current_dir, temporada_actual)

    logger.info("")
    logger.info("=== Resumen de migración ===")
    logger.info("%-25s %-12s %s", "tabla", "temporada", "filas")
    for table, temporada, rows in summary:
        logger.info("%-25s %-12s %d", table, temporada, rows)


if __name__ == "__main__":
    main()
