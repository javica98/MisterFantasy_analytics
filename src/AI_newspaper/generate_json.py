import pandas as pd
from datetime import datetime, timedelta

from src.utils.team_map import map_team, map_position


def clasificacion_dict(df: pd.DataFrame) -> dict:
    """
    Convierte un DataFrame de clasificación en un dict indexado por manager.

    Args:
        df: DataFrame con columnas ``nombre`` y ``puntos``. Puede contener
            varias filas por manager (una por jornada); los puntos se acumulan.

    Returns:
        ``{manager: {"puntos": int, "posicion": int}}`` ordenado por puntos
        descendentes (posición 1 = líder).

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame([{"nombre": "Maldinillo", "puntos": 120},
        ...                    {"nombre": "Dani", "puntos": 100}])
        >>> result = clasificacion_dict(df)
        >>> result["Maldinillo"]["posicion"]
        1
    """
    out = (
        df.groupby("nombre", as_index=False)["puntos"]
          .sum()
          .sort_values("puntos", ascending=False)
    )
    out["posicion"] = range(1, len(out) + 1)
    return out.set_index("nombre")[["puntos", "posicion"]].to_dict("index")

def generate_json_for_jornada(
    jornada_num: int,
    fecha_transfers_start,
    fecha_jornada_end,
    df_clean: pd.DataFrame,
    df_gameweek: pd.DataFrame,
    df_clasificacion: pd.DataFrame,
    df_quinielas: pd.DataFrame,
) -> dict:
    """
    Genera el JSON estructurado para una jornada concreta del backfill.

    - jornada_num: número de jornada
    - fecha_transfers_start: fecha desde la que incluir transfers (fin de la jornada anterior)
    - fecha_jornada_end: fecha fin de esta jornada
    - Clasificación acumulada hasta jornada_num
    """
    # Gameweek solo de esta jornada
    df_gw = df_gameweek[df_gameweek["Jornada"] == jornada_num].copy()

    fecha_inicio = df_gw["Date"].min() if not df_gw.empty else fecha_jornada_end

    # Transfers en la ventana (fin jornada anterior -> fin jornada actual)
    df_clean = df_clean.copy()
    df_clean["fecha"] = pd.to_datetime(df_clean["fecha"], errors="coerce")
    df_t = df_clean[
        (df_clean["fecha"].dt.date > fecha_transfers_start)
        & (df_clean["fecha"].dt.date <= fecha_jornada_end)
    ]

    # Clasificación acumulada hasta esta jornada
    df_clas_acum = df_clasificacion[df_clasificacion["jornada"] <= jornada_num]
    df_class_gen = clasificacion_dict(df_clas_acum)
    df_class_jor = clasificacion_dict(df_clasificacion[df_clasificacion["jornada"] == jornada_num])

    df_quin_acum = df_quinielas[df_quinielas["jornada"] <= jornada_num]
    df_quin_gen = clasificacion_dict(df_quin_acum)
    df_quin_jor = clasificacion_dict(df_quinielas[df_quinielas["jornada"] == jornada_num])

    # Transfers
    transfers = []
    for _, row in df_t.iterrows():
        if pd.isna(row["jugador"]) or row["jugador"] == "":
            continue
        manager = row["equipo"]
        transfers.append({
            "fecha": str(row["fecha"].date()),
            "subtype": row["subtype"],
            "equipo": manager,
            "ganancias": row["ganancias"],
            "jugador": row["jugador"],
            "compra_venta": row["compra-venta"],
            "equipo_jugador": map_team(row["equipoLiga"]),
            "clasificacion_manager_general": df_class_gen.get(manager, {"puntos": 0, "posicion": 9}),
            "clasificacion_manager_jornada": df_class_jor.get(manager, {"puntos": 0, "posicion": 9}),
        })

    # Gameweek
    gameweek = []
    for _, row in df_gw.iterrows():
        manager = row["Manager"]
        gameweek.append({
            "fecha": str(pd.to_datetime(row["Date"]).date()),
            "jornada": int(row["Jornada"]),
            "equipo_local": map_team(row["EquipoLocal"]),
            "resultado_local": row["ResultadoLocal"],
            "equipo_visitante": map_team(row["EquipoVisitante"]),
            "resultado_visitante": row["ResultadoVisitante"],
            "equipo_jugador": map_team(row["EquipoJugador"]),
            "manager": manager,
            "clasificacion_manager_general": df_class_gen.get(manager, {"puntos": 0, "posicion": 9}),
            "clasificacion_manager_jornada": df_class_jor.get(manager, {"puntos": 0, "posicion": 9}),
            "jugador": row["NombreJugador"],
            "posicion": map_position(row["Posicion"]),
            "puntos": row["Puntos"],
            "suplente": row["Suplente"],
            "cambio": row["Cambio"],
            "goles": row["Goles"],
            "asistencias": row["Asistencias"],
            "gol_propia": row["GolPropia"],
            "penalti_marcado": row["PenaltiMarcado"],
            "penalti_fallado": row["PenaltiFallado"],
            "penalti_parado": row["PenaltiParado"],
            "amarilla": row["Amarilla"],
            "roja": row["Roja"],
        })

    return {
        "jornada": jornada_num,
        "fecha_inicio": str(fecha_inicio) if not isinstance(fecha_inicio, str) else fecha_inicio,
        "fecha_fin": str(fecha_jornada_end),
        "transfers": transfers,
        "gameweek": gameweek,
        "clasificacion": {"general": df_class_gen, "jornada": df_class_jor},
        "quinielas": {"general": df_quin_gen, "jornada": df_quin_jor},
    }


def generate_json(last_days: int, df_clean: pd.DataFrame, df_gameweek: pd.DataFrame,df_clasificacion: pd.DataFrame,df_quinielas: pd.DataFrame):
    """
    Recibe:
        last_days: número de días atrás para filtrar los datos
        df_clean: DataFrame de compras/ventas (transfers)
        df_gameweek: DataFrame de gameweek/puntuaciones

    Devuelve:
        JSON estructurado de los últimos `last_days` días
    """
    # ---------------------
    # Determinar rango de fechas
    # ---------------------
    today = datetime.now().date()
    cutoff_date = today - timedelta(days=last_days)

    # Filtrar transfers
    df_transfers_filtered = df_clean[pd.to_datetime(df_clean['fecha']).dt.date >= cutoff_date]

    # Filtrar gameweek
    df_gameweek_filtered = df_gameweek[pd.to_datetime(df_gameweek['Date']).dt.date >= cutoff_date]

    #Clasificacion general y jornada

    jornadas=df_gameweek_filtered["Jornada"].unique()
    df_class_gen = clasificacion_dict(df_clasificacion)
    df_class_jor = clasificacion_dict(
        df_clasificacion[df_clasificacion["jornada"].isin(jornadas)]
    )
    #Quinielas general y jornada

    df_quin_gen = clasificacion_dict(df_quinielas)
    df_quin_jor = clasificacion_dict(
        df_quinielas[df_quinielas["jornada"].isin(jornadas)]
    )
    # ---------------------
    # Procesar transfers
    # ---------------------
    transfers = []
    for _, row in df_transfers_filtered.iterrows():
        if pd.isna(row['jugador']) or row['jugador'] == "":
            continue
        transfers.append({
            "fecha": row['fecha'],
            "subtype": row['subtype'],
            "equipo": row['equipo'],
            "ganancias": row['ganancias'],
            "jugador": row['jugador'],
            "compra_venta": row['compra-venta'],
            "equipo_jugador": map_team(row["equipoLiga"]),
            "clasificacion_manager_general": df_class_gen.get(row['equipo'], {"puntos": 0, "posicion": 9}),
            "clasificacion_manager_jornada": df_class_jor.get(row['equipo'], {"puntos": 0, "posicion": 9})
        })

    # ---------------------
    # Procesar gameweek
    # ---------------------
    gameweek = []
    for _, row in df_gameweek_filtered.iterrows():
        gameweek.append({
            "fecha": row['Date'],
            "jornada": row['Jornada'],
            "equipo_local": map_team(row['EquipoLocal']),
            "resultado_local": row['ResultadoLocal'],
            "equipo_visitante": map_team(row['EquipoVisitante']),
            "resultado_visitante": row['ResultadoVisitante'],
            "equipo_jugador": map_team(row['EquipoJugador']),
            "manager": row['Manager'],
            "clasificacion_manager_general": df_class_gen.get(row['Manager'], {"puntos": 0, "posicion": 9}),
            "clasificacion_manager_jornada": df_class_jor.get(row['Manager'], {"puntos": 0, "posicion": 9}),
            "jugador": row['NombreJugador'],
            "posicion": map_position(row['Posicion']),
            "puntos": row['Puntos'],
            "suplente": row['Suplente'],
            "cambio": row['Cambio'],
            "goles": row['Goles'],
            "asistencias": row['Asistencias'],
            "gol_propia": row['GolPropia'],
            "penalti_marcado": row['PenaltiMarcado'],
            "penalti_fallado": row['PenaltiFallado'],
            "penalti_parado": row['PenaltiParado'],
            "amarilla": row['Amarilla'],
            "roja": row['Roja']
        })
    # ---------------------
    # Procesar clasificacion
    # ---------------------
    clasificacion = {
    "general": df_class_gen,
    "jornada": df_class_jor
    }
    quinielas = {
    "general": df_quin_gen,
    "jornada": df_quin_jor
    }

    # ---------------------
    # JSON final
    # ---------------------
    final_json = {
        "fecha_inicio": str(cutoff_date),
        "fecha_fin": str(today),
        "transfers": transfers,
        "gameweek": gameweek,
        "clasificacion": clasificacion,
        "quinielas":quinielas
    }

    return final_json
