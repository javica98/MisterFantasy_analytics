import pandas as pd
import logging

logger = logging.getLogger(__name__)

def merge_gameweek(df_viejo: pd.DataFrame, df_nuevo: pd.DataFrame) -> pd.DataFrame:
    """
    Añade a df_viejo solo las filas nuevas de df_nuevo.
    La columna Date NO se usa para detectar duplicados.
    """

    try:
        if df_viejo is None or df_viejo.empty:
            return df_nuevo.copy()

        if df_nuevo is None or df_nuevo.empty:
            return df_viejo.copy()

        # Columnas que identifican una fila única (SIN Date)
        subset_cols = [
            "Jornada",
            "EquipoLocal",
            "EquipoVisitante",
            "EquipoJugador",
            "Manager",
            "NombreJugador"
        ]

        # Verificación defensiva
        for col in subset_cols:
            if col not in df_viejo.columns or col not in df_nuevo.columns:
                raise ValueError(f"Falta la columna '{col}' en uno de los DataFrames")

        # Concatenar y eliminar duplicados
        df_final = (
            pd.concat([df_viejo, df_nuevo], ignore_index=True)
              .drop_duplicates(subset=subset_cols, keep="first")
              .reset_index(drop=True)
        )

        logger.info(
            f"Merge gameweek OK | "
            f"Viejo: {len(df_viejo)} | "
            f"Nuevo recibido: {len(df_nuevo)} | "
            f"Total final: {len(df_final)}"
        )

        return df_final

    except Exception as e:
        logger.exception(f"Error durante el merge de gameweek: {e}")
        return df_viejo.copy()
