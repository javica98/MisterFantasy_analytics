import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Un partido de una jornada (la Date NO forma parte de la clave).
MATCH_KEY = ["Jornada", "EquipoLocal", "EquipoVisitante"]


def merge_gameweek(df_viejo: pd.DataFrame, df_nuevo: pd.DataFrame) -> pd.DataFrame:
    """
    Upsert por partido: si un partido (Jornada, EquipoLocal, EquipoVisitante)
    viene en df_nuevo, sus filas sustituyen por completo a las de df_viejo;
    los partidos que no vienen se conservan tal cual.

    Antes se usaba drop_duplicates(keep="first"), que congelaba los puntos
    de la primera lectura: Mister corrige puntos días después del partido y
    esas correcciones nunca llegaban a la BD.
    """
    try:
        if df_nuevo is None or df_nuevo.empty:
            return df_viejo.copy() if df_viejo is not None else pd.DataFrame()

        if df_viejo is None or df_viejo.empty:
            return df_nuevo.copy()

        for col in MATCH_KEY:
            if col not in df_viejo.columns or col not in df_nuevo.columns:
                raise ValueError(f"Falta la columna '{col}' en uno de los DataFrames")

        nuevos = df_nuevo[MATCH_KEY].drop_duplicates()
        marcado = df_viejo.merge(nuevos, on=MATCH_KEY, how="left", indicator=True)["_merge"]
        df_viejo_filtrado = df_viejo[(marcado == "left_only").to_numpy()]

        df_final = (
            pd.concat([df_viejo_filtrado, df_nuevo], ignore_index=True)
              .sort_values(["Jornada", "Date"], kind="stable")
              .reset_index(drop=True)
        )

        logger.info(
            f"Merge gameweek OK | "
            f"Viejo: {len(df_viejo)} | "
            f"Partidos actualizados: {len(nuevos)} | "
            f"Filas sustituidas: {len(df_viejo) - len(df_viejo_filtrado)} | "
            f"Nuevas recibidas: {len(df_nuevo)} | "
            f"Total final: {len(df_final)}"
        )

        return df_final

    except Exception as e:
        logger.exception(f"Error durante el merge de gameweek: {e}")
        return df_viejo.copy()
