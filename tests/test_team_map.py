"""
Tests de map_team: mapa fijo + nombres de respaldo desde la tabla `partidos`.
"""
import pandas as pd

from src.utils import db as db_utils
from src.utils import team_map


def test_ascendidos_2026_27_tienen_nombre():
    assert team_map.map_team(1490) == "Racing de Santander"
    assert team_map.map_team(6.0) == "RC Deportivo"  # equipoLiga llega como float
    assert team_map.map_team(13) == "Málaga CF"


def test_equipo_desconocido_usa_el_nombre_de_partidos(tmp_path, monkeypatch):
    monkeypatch.setattr(db_utils, "get_db_path", lambda: tmp_path / "t.db")
    monkeypatch.setattr(team_map, "_nombres_api", None)
    pd.DataFrame([{"id_local": 777, "local": "Nuevo Ascendido", "id_visitante": 15,
                   "visitante": "Real Madrid", "temporada": "2027-28"}]).to_sql(
        "partidos", db_utils.get_connection(), index=False)
    assert team_map.map_team(777) == "Nuevo Ascendido"
    assert team_map.map_team(777.0) == "Nuevo Ascendido"
    assert team_map.map_team(15) == "Real Madrid"  # manda TEAM_MAP
    assert team_map.map_team(9999) == 9999


def test_sin_tabla_partidos_devuelve_el_id(tmp_path, monkeypatch):
    monkeypatch.setattr(db_utils, "get_db_path", lambda: tmp_path / "vacia.db")
    monkeypatch.setattr(team_map, "_nombres_api", None)
    assert team_map.map_team(777) == 777
