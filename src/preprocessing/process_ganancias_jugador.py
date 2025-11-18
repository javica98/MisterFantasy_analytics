import pandas as pd
import numpy as np

def procesar_ganancias_jugador(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra el DataFrame para operaciones de 'transfer' o 'venta',
    elimina columnas innecesarias y calcula la columna 'Diff' 
    como diferencia de ganancias con filas relacionadas.
    """
    # Filtrar filas relevantes
    df_filtrado = df[(df['type'] == 'transfer') & (df['compra-venta'] == 'venta') & (df['subtype'] != 'Puja')].copy()

    # Crear columna 'Diff' inicialmente vacía
    df_filtrado["Diff"] = np.nan

    # Función para calcular Diff para cada fila
    def calcular_diff(row):
        # Filtrar filas relacionadas en df original
        df_row = df[
            (df['type'] == 'transfer') &
            (df['id'] > row['id']) &
            (df['equipo'] == row['equipo']) &
            (df['jugador'] == row['jugador']) &
            (df['compra-venta'] == 'compra')
        ]
        if df_row.empty:
            return np.nan
        # Ejemplo de cálculo: diferencia entre la suma de ganancias de df_row y la fila actual

        return row['ganancias'] + df_row['ganancias'].iloc[0]

    # Aplicar la función fila por fila
    df_filtrado['Diff'] = df_filtrado.apply(calcular_diff, axis=1)

    # Eliminar columnas innecesarias
    df_filtrado = df_filtrado.drop(["id","type","ganancias","compra-venta"], axis=1, errors='ignore')
    df_filtrado = df_filtrado.dropna(subset=['Diff'])

    return df_filtrado
