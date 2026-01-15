import pandas as pd
import logging

logger = logging.getLogger(__name__)

def merge_quinielas(df_viejo: pd.DataFrame, df_nuevo: pd.DataFrame) -> pd.DataFrame:
    """
    Fusiona clasificaciones antiguas y nuevas eliminando jornadas duplicadas.

    - Si una jornada del nuevo CSV ya existe en el viejo, se reemplaza.
    - Si ocurre un error, se devuelve el viejo sin cambios.

    Parámetros:
        df_viejo (pd.DataFrame): DataFrame con clasificaciones antiguas.
        df_nuevo (pd.DataFrame): DataFrame con clasificaciones nuevas.

    Retorna:
        pd.DataFrame: DataFrame combinado y limpio.
    """
    try:
        # Validación de columnas
        if 'jornada' not in df_nuevo.columns or 'jornada' not in df_viejo.columns:
            raise ValueError("Ambos DataFrames deben tener una columna 'jornada'")

        # Identificar jornadas nuevas
        jornadas_nuevas = df_nuevo['jornada'].unique()
        logger.debug(f"Jornadas nuevas detectadas: {jornadas_nuevas}")

        # Filtrar el viejo para eliminar esas jornadas
        df_viejo_filtrado = df_viejo[~df_viejo['jornada'].isin(jornadas_nuevas)]
        logger.info(f"Se eliminaron {len(df_viejo) - len(df_viejo_filtrado)} filas de jornadas antiguas duplicadas.")

        # Concatenar viejo filtrado + nuevo
        df_final = pd.concat([df_viejo_filtrado, df_nuevo], ignore_index=True)

        logger.info(f"Merge completado correctamente. Total filas: {len(df_final)}.")
        return df_final

    except Exception as e:
        logger.exception(f"Error durante el merge de clasificaciones: {e}")
        return df_viejo.copy()
