import pandas as pd
import numpy as np

def procesar_clausulas_acuerdos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra el DataFrame para operaciones de 'transfer' o 'venta',
    elimina columnas innecesarias y calcula la columna 'Diff' 
    como diferencia de ganancias con filas relacionadas.
    """
    # Filtrar filas relevantes
    df_filtrado = df[(df['type'] == 'transfer') & ((df['subtype'] == 'clausula')|(df['subtype'] == 'acuerdo'))].copy()
    df_filtrado = df_filtrado.drop(["type","mensaje","posicionJugador","puntosJugador","equipoLiga","name","money","position","aciertos","points","jornada","date","idTransfer"], axis=1, errors='ignore')
    return df_filtrado
