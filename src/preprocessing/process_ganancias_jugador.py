import pandas as pd

def procesar_ganancias_jugador(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra el DataFrame para operaciones de 'transfer' de venta (no Puja),
    y calcula la columna 'Diff' como la ganancia neta de cada operación
    (precio de venta + precio de compra, donde compra es negativo).

    La compra de referencia es la primera compra del mismo jugador/equipo
    con id mayor que la venta (la compra más reciente en el historial).
    """
    # Ventas relevantes
    df_ventas = df[
        (df['type'] == 'transfer') &
        (df['compra-venta'] == 'venta') &
        (df['subtype'] != 'Puja')
    ].copy()

    # Compras relevantes
    df_compras = df[
        (df['type'] == 'transfer') &
        (df['compra-venta'] == 'compra')
    ][['id', 'equipo', 'jugador', 'ganancias']].copy()
    df_compras = df_compras.rename(columns={'id': 'id_compra', 'ganancias': 'ganancias_compra'})

    # Para cada venta, buscar la compra del mismo jugador/equipo con id_compra > id_venta.
    # Hacemos un merge cruzado por jugador+equipo y luego filtramos y cogemos el mínimo id_compra.
    merged = df_ventas[['id', 'equipo', 'jugador', 'ganancias']].merge(
        df_compras,
        on=['equipo', 'jugador'],
        how='left'
    )
    # Solo compras posteriores a la venta (id mayor = más antiguo en el historial)
    merged = merged[merged['id_compra'] > merged['id']]

    # La compra de referencia es la primera (id_compra mínimo entre las válidas)
    merged = (
        merged.sort_values('id_compra')
        .groupby(['id', 'equipo', 'jugador'], as_index=False)
        .first()
    )

    # Calcular Diff = ganancia_venta + ganancia_compra (compra es negativa, así que suma)
    merged['Diff'] = merged['ganancias'] + merged['ganancias_compra']

    # Unir Diff al DataFrame de ventas original
    df_ventas = df_ventas.merge(
        merged[['id', 'equipo', 'jugador', 'Diff']],
        on=['id', 'equipo', 'jugador'],
        how='left'
    )

    # Eliminar columnas innecesarias y filas sin Diff
    df_ventas = df_ventas.drop(["id", "type", "ganancias", "compra-venta"], axis=1, errors='ignore')
    df_ventas = df_ventas.dropna(subset=['Diff'])

    return df_ventas
