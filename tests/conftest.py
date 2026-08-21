"""
Fixtures compartidos para todos los tests de MisterFantasy Analytics.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

# Aseguramos que el root del proyecto esté en sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────
# Fixtures: DataFrames de ejemplo
# ─────────────────────────────────────────────

@pytest.fixture
def df_gameweek():
    """DataFrame mínimo de gameweek con 3 jugadores."""
    return pd.DataFrame([
        {
            "Date": "2026-03-01", "Jornada": 25,
            "EquipoLocal": 15, "ResultadoLocal": 2,
            "EquipoVisitante": 3, "ResultadoVisitante": 1,
            "EquipoJugador": 15, "Manager": "Maldinillo",
            "NombreJugador": "K. Mbappé", "Posicion": 4,
            "Puntos": 18, "Suplente": 0, "Cambio": 0,
            "Goles": 2, "Asistencias": 1,
            "GolPropia": 0, "PenaltiMarcado": 0, "PenaltiFallado": 0,
            "PenaltiParado": 0, "Amarilla": 0, "Roja": 0,
        },
        {
            "Date": "2026-03-01", "Jornada": 25,
            "EquipoLocal": 15, "ResultadoLocal": 2,
            "EquipoVisitante": 3, "ResultadoVisitante": 1,
            "EquipoJugador": 3, "Manager": "Dani",
            "NombreJugador": "Raphinha", "Posicion": 4,
            "Puntos": 12, "Suplente": 0, "Cambio": 0,
            "Goles": 1, "Asistencias": 1,
            "GolPropia": 0, "PenaltiMarcado": 0, "PenaltiFallado": 0,
            "PenaltiParado": 0, "Amarilla": 0, "Roja": 0,
        },
        {
            "Date": "2026-03-01", "Jornada": 25,
            "EquipoLocal": 2, "ResultadoLocal": 0,
            "EquipoVisitante": 20, "ResultadoVisitante": 3,
            "EquipoJugador": 2, "Manager": "Los marinero",
            "NombreJugador": "T. Lemar", "Posicion": 3,
            "Puntos": 2, "Suplente": 0, "Cambio": 0,
            "Goles": 0, "Asistencias": 0,
            "GolPropia": 0, "PenaltiMarcado": 0, "PenaltiFallado": 0,
            "PenaltiParado": 0, "Amarilla": 1, "Roja": 0,
        },
    ])


@pytest.fixture
def df_gameweek_with_events():
    """DataFrame con tarjeta roja, penalti parado y gol en propia."""
    return pd.DataFrame([
        {
            "Date": "2026-03-01", "Jornada": 25,
            "EquipoLocal": 15, "ResultadoLocal": 1,
            "EquipoVisitante": 3, "ResultadoVisitante": 0,
            "EquipoJugador": 15, "Manager": "Maldinillo",
            "NombreJugador": "K. Mbappé", "Posicion": 4,
            "Puntos": 14, "Suplente": 0, "Cambio": 0,
            "Goles": 1, "Asistencias": 0,
            "GolPropia": 0, "PenaltiMarcado": 0, "PenaltiFallado": 0,
            "PenaltiParado": 0, "Amarilla": 0, "Roja": 1,  # roja
        },
        {
            "Date": "2026-03-01", "Jornada": 25,
            "EquipoLocal": 15, "ResultadoLocal": 1,
            "EquipoVisitante": 3, "ResultadoVisitante": 0,
            "EquipoJugador": 3, "Manager": "Dani",
            "NombreJugador": "ter Stegen", "Posicion": 1,
            "Puntos": 10, "Suplente": 0, "Cambio": 0,
            "Goles": 0, "Asistencias": 0,
            "GolPropia": 0, "PenaltiMarcado": 0, "PenaltiFallado": 0,
            "PenaltiParado": 1, "Amarilla": 0, "Roja": 0,  # penalti parado
        },
        {
            "Date": "2026-03-01", "Jornada": 25,
            "EquipoLocal": 2, "ResultadoLocal": 0,
            "EquipoVisitante": 15, "ResultadoVisitante": 2,
            "EquipoJugador": 2, "Manager": "Los marinero",
            "NombreJugador": "T. Lemar", "Posicion": 3,
            "Puntos": -1, "Suplente": 0, "Cambio": 0,
            "Goles": 0, "Asistencias": 0,
            "GolPropia": 1, "PenaltiMarcado": 0, "PenaltiFallado": 0,
            "PenaltiParado": 0, "Amarilla": 0, "Roja": 0,  # gol en propia
        },
    ])


@pytest.fixture
def df_transfers():
    """DataFrame mínimo de transfers."""
    return pd.DataFrame([
        {
            "fecha": "2026-03-01", "id": 0,
            "type": "transfer", "subtype": "clausula",
            "equipo": "Maldinillo", "ganancias": -56.0,
            "jugador": "Raphinha", "compra-venta": "compra",
            "equipoLiga": 3,
        },
        {
            "fecha": "2026-03-01", "id": 1,
            "type": "transfer", "subtype": "mercado",
            "equipo": "Dani", "ganancias": 20.0,
            "jugador": "T. Lemar", "compra-venta": "venta",
            "equipoLiga": 2,
        },
        {
            "fecha": "2026-03-01", "id": 2,
            "type": "transfer", "subtype": "mercado",
            "equipo": "Los marinero", "ganancias": -8.0,
            "jugador": "K. Mbappé", "compra-venta": "compra",
            "equipoLiga": 15,
        },
    ])


@pytest.fixture
def df_clasificacion():
    """DataFrame de clasificación acumulada."""
    return pd.DataFrame([
        {"nombre": "Maldinillo", "puntos": 120, "jornada": 25},
        {"nombre": "Dani",       "puntos": 115, "jornada": 25},
        {"nombre": "Los marinero", "puntos": 90, "jornada": 25},
    ])


@pytest.fixture
def df_quinielas():
    """DataFrame de quinielas."""
    return pd.DataFrame([
        {"nombre": "Maldinillo", "puntos": 10, "jornada": 25},
        {"nombre": "Dani",       "puntos":  8, "jornada": 25},
        {"nombre": "Los marinero", "puntos": 6, "jornada": 25},
    ])


@pytest.fixture
def sample_events_json(df_transfers, df_gameweek, df_clasificacion, df_quinielas):
    """JSON de eventos típico como lo genera generate_json."""
    from src.AI_newspaper.generate_json import map_team, map_position, clasificacion_dict
    df_class_gen = clasificacion_dict(df_clasificacion)
    df_class_jor = clasificacion_dict(df_clasificacion)

    transfers = []
    for _, row in df_transfers.iterrows():
        transfers.append({
            "fecha": str(row["fecha"]),
            "subtype": row["subtype"],
            "equipo": row["equipo"],
            "ganancias": row["ganancias"],
            "jugador": row["jugador"],
            "compra_venta": row["compra-venta"],
            "equipo_jugador": map_team(row["equipoLiga"]),
            "clasificacion_manager_general": df_class_gen.get(row["equipo"], {"puntos": 0, "posicion": 9}),
            "clasificacion_manager_jornada": df_class_jor.get(row["equipo"], {"puntos": 0, "posicion": 9}),
        })

    gameweek = []
    for _, row in df_gameweek.iterrows():
        gameweek.append({
            "fecha": str(row["Date"]),
            "jornada": int(row["Jornada"]),
            "equipo_jugador": map_team(int(row["EquipoJugador"])),
            "manager": row["Manager"],
            "clasificacion_manager_general": df_class_gen.get(row["Manager"], {"puntos": 0, "posicion": 9}),
            "clasificacion_manager_jornada": df_class_jor.get(row["Manager"], {"puntos": 0, "posicion": 9}),
            "jugador": row["NombreJugador"],
            "posicion": map_position(int(row["Posicion"])),
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
        "transfers": transfers,
        "gameweek": gameweek,
        "clasificacion": {"general": df_class_gen, "jornada": df_class_jor},
        "quinielas": {"general": {}, "jornada": {}},
    }
