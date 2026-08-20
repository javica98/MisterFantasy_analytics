"""
export_db_to_csv.py
====================
Exporta las tablas de data/mister.db a CSV, filtradas por temporada, para
inspección manual o depuración puntual. No forma parte del pipeline ni de CI.

Uso:
    python scripts/export_db_to_csv.py [temporada] [directorio_salida]

Si se omite `temporada`, usa la temporada activa (config.yaml -> season.current).
Si se omite `directorio_salida`, exporta a data/export/<temporada>/.
"""

import sys
import sqlite3
import logging
from pathlib import Path

# ── Entorno ───────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.utils import db as db_utils

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def _list_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cur.fetchall()]


def main():
    temporada = sys.argv[1] if len(sys.argv) > 1 else db_utils.get_active_season()
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT_DIR / "data" / "export" / temporada
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Exportando temporada '%s' desde %s a %s", temporada, db_utils.get_db_path(), out_dir)

    with db_utils.get_connection() as conn:
        tables = _list_tables(conn)

    if not tables:
        logger.warning("No hay tablas en la base de datos.")
        return

    for table in sorted(tables):
        df = db_utils.read_table(table, temporada=temporada)
        if df.empty:
            logger.info("  %s: 0 filas, se omite", table)
            continue
        out_path = out_dir / f"{table}.csv"
        df.to_csv(out_path, index=False)
        logger.info("  %s: %d filas -> %s", table, len(df), out_path)


if __name__ == "__main__":
    main()
