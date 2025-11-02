import pandas as pd
import logging

logger = logging.getLogger(__name__)

def normalize_date_column(df, column_name="date"):
    """
    Convierte una columna de fechas a datetime y elimina la parte de hora.
    Si no existe la columna, no hace nada.
    """
    if column_name not in df.columns:
        logger.warning(f"Columna '{column_name}' no encontrada en DataFrame.")
        return df

    try:
        df[column_name] = pd.to_datetime(df[column_name], errors="coerce").dt.date
        logger.info(f"✅ Columna '{column_name}' normalizada correctamente.")
    except Exception as e:
        logger.error(f"Error al normalizar columna '{column_name}': {e}")

    return df
