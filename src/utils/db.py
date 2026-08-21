import sqlite3
import logging
from pathlib import Path

import pandas as pd

from src.utils.config_loader import get_base_dir, load_config

logger = logging.getLogger(__name__)

# Tablas que existen como CSV de trabajo pero no deben pasar por la BD
# (artefactos de pruebas/desarrollo, no datos de temporada reales).
_EXCLUDED_TABLES = {"test"}


def known_tables() -> set:
    """Nombres de tabla derivados de config.yaml -> paths.csv.* (stem del archivo)."""
    cfg = load_config(validate_env=False)
    csv_paths = cfg.get("paths", {}).get("csv", {})
    return {Path(p).stem for p in csv_paths.values()} - _EXCLUDED_TABLES


def get_db_path() -> Path:
    cfg = load_config(validate_env=False)
    db_path = cfg.get("data", {}).get("db_path", "data/mister.db")
    return get_base_dir() / db_path


def get_connection() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def get_active_season() -> str:
    cfg = load_config(validate_env=False)
    return cfg["season"]["current"]


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def read_table(table: str, temporada: str | None = None) -> pd.DataFrame:
    """Lee una tabla de la BD, opcionalmente filtrada por temporada.

    Devuelve DataFrame vacío si la tabla todavía no existe (misma semántica
    que safe_read_csv con un archivo inexistente).
    """
    with get_connection() as conn:
        if not table_exists(conn, table):
            logger.warning(f"Tabla no encontrada, devolviendo vacío: {table}")
            return pd.DataFrame()
        if temporada is None:
            return pd.read_sql_query(f"SELECT * FROM {table}", conn)
        return pd.read_sql_query(
            f"SELECT * FROM {table} WHERE temporada = ?", conn, params=(temporada,)
        )


# Si una tabla ya tiene al menos este número de filas para la temporada,
# una escritura nueva que traiga menos de MIN_KEEP_RATIO de esas filas se
# rechaza por defecto (probable fallo silencioso aguas arriba, no una
# reducción real de datos).
_SHRINK_GUARD_MIN_ROWS = 10
_SHRINK_GUARD_MIN_KEEP_RATIO = 0.5


def write_table(df: pd.DataFrame, table: str, temporada: str, allow_shrink: bool = False) -> bool:
    """Sobreescribe las filas de una temporada en una tabla.

    Reproduce el patrón actual de los scripts (leer todo, concatenar/deduplicar
    en pandas, sobreescribir el archivo entero) pero acotado a la temporada,
    en vez de al fichero completo. Idempotente: se puede volver a llamar sin
    duplicar filas.

    Antes de borrar y reescribir, compara el tamaño del DataFrame nuevo contra
    las filas que ya existen para esa temporada. Si el nuevo trae sospechosamente
    menos (por defecto, menos de la mitad, y solo si ya había >= 10 filas),
    rechaza la escritura en vez de arriesgarse a borrar datos reales por un
    fallo silencioso aguas arriba (extracción/preprocesado que produjo un
    DataFrame vacío o truncado). Pasa allow_shrink=True para casos legítimos
    (ej. reimportar una migración desde cero).

    Devuelve True si escribió, False si rechazó la escritura o falló.
    """
    df = df.copy()
    df["temporada"] = temporada
    try:
        with get_connection() as conn:
            existing_rows = 0
            if table_exists(conn, table):
                cur = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE temporada = ?", (temporada,)
                )
                existing_rows = cur.fetchone()[0]

            if (
                not allow_shrink
                and existing_rows >= _SHRINK_GUARD_MIN_ROWS
                and len(df) < existing_rows * _SHRINK_GUARD_MIN_KEEP_RATIO
            ):
                logger.error(
                    f"Escritura rechazada: tabla={table} temporada={temporada} tiene "
                    f"{existing_rows} filas y el DataFrame nuevo solo trae {len(df)} "
                    f"(< {_SHRINK_GUARD_MIN_KEEP_RATIO:.0%}). Probable fallo silencioso "
                    f"aguas arriba; usa allow_shrink=True si es intencional."
                )
                return False

            if table_exists(conn, table):
                conn.execute(f"DELETE FROM {table} WHERE temporada = ?", (temporada,))
            df.to_sql(table, conn, if_exists="append", index=False)
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_temporada ON {table}(temporada)"
            )
            conn.commit()
        logger.info(f"Guardado en BD: tabla={table} temporada={temporada} filas={len(df)}")
        return True
    except Exception as e:
        logger.error(f"Error al guardar tabla {table} (temporada={temporada}): {e}")
        return False
