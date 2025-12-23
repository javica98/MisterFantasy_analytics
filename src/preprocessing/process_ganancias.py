import pandas as pd

def procesar_ganancias(df: pd.DataFrame) -> pd.DataFrame:
    """
    Procesa el CSV de ganancias, limpiando registros y estandarizando.

    Args:
        filepath (str): Ruta al CSV de ganancias (ej. 'ganancias.csv').

    Returns:
        pd.DataFrame: DataFrame con datos procesados.
    """

    # Eliminar start_mercado seguido de transfer con de_equipo != 'Mister'
    filas_a_eliminar = []
    for i in range(len(df) - 1):
        fila_actual = df.loc[i]
        fila_siguiente = df.loc[i + 1]
        if (
            fila_actual["subtype"] == "start_mercado"
            and fila_siguiente["type"] == "transfer"
            and str(fila_siguiente.get("de_equipo", "")) != "Mister"
        ):
            filas_a_eliminar.append(i)
    df = df.drop(filas_a_eliminar).reset_index(drop=True)

    registros = []
    new_id = 0
    bool_new_id = False

    for _, row in df.iterrows():
        fecha = row['date']
        if bool_new_id and row["de_equipo"]!="Mister":
            new_id =new_id +1
            bool_new_id = False
        tipo = row["type"]
        subtipo = row["subtype"]
        if subtipo == "start_mercado":
            bool_new_id = True
            registros.append({
                "fecha":fecha,
                "id": new_id,
                "type": tipo,
                "subtype": subtipo,
                "equipo": "Mercado diario",
                "ganancias": 0
            })
        elif subtipo == "start_jornada":
            registros.append({
                "fecha":fecha,
                "id": new_id,
                "type": tipo,
                "subtype": subtipo,
                "equipo": row["jornada"],
                "ganancias": 0
            })
        elif tipo in ["bonificacion"]:
            if pd.notna(row.get("money")):
                ganancia = row["money"]
            else:
                ganancia = 0
            registros.append({
                "fecha":fecha,
                "id": new_id,
                "type": tipo,
                "subtype": subtipo,
                "equipo": row["name"],
                "ganancias": ganancia
            })
        elif tipo == "transfer":
            try:
                jugador = row["jugador"]
                de_equipo = row["de_equipo"]
                a_equipo = row["a_equipo"]

                if pd.isna(a_equipo):
                    registros.append({
                        "fecha":fecha,
                        "id": new_id,
                        "type": "bajadaclausula",
                        "equipo": de_equipo,
                        "jugador": jugador,
                        "ganancias": 0
                    })
                else:
                    precio = row["precio"]
                    if subtipo == "Puja":
                        precio = 0
                    registros.append({
                        "fecha":fecha,
                        "id": new_id,
                        "type": "transfer",
                        "subtype": subtipo,
                        "equipo": de_equipo,
                        "jugador": jugador,
                        "compra-venta": "venta",
                        "ganancias": precio
                    })
                    registros.append({
                        "fecha":fecha,
                        "id": new_id,
                        "type": "transfer",
                        "subtype": subtipo,
                        "equipo": a_equipo,
                        "jugador": jugador,
                        "compra-venta": "compra",
                        "ganancias": -precio
                    })
            except Exception as e:
                print(f"Error procesando fila de transferencia: {row}\n{e}")

    df_limpio = pd.DataFrame(registros)

    # Filtrar filas donde equipo NO sea "Mister"
    df_limpio = df_limpio[df_limpio["equipo"] != "Mister"]

    return df_limpio
