"""
Tests de scripts/validate_data.py sobre una BD SQLite temporal con datos sintéticos.
"""
import sqlite3
from datetime import date

import pandas as pd
import pytest

from scripts.validate_data import (
    Informe, check_clasificaciones, check_continuidad, check_duplicados, check_encogimiento,
    check_gameweek_vs_calendario,
)

T = "2026-27"


def _tabla(conn, nombre, filas):
    pd.DataFrame(filas).assign(temporada=T).to_sql(nombre, conn, index=False, if_exists="append")


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


def _snapshots(conn, dias):
    for tabla in ("mercado", "subidasBajadas", "jornadas"):
        _tabla(conn, tabla, [{"date": d, "jornada": 1} for d in dias])


class TestContinuidad:
    def test_detecta_hueco_y_respeta_dias_perdidos(self, conn):
        _snapshots(conn, ["2026-08-16", "2026-08-18", "2026-08-20"])
        inf = Informe()
        check_continuidad(conn, T, date(2026, 8, 20), ["2026-08-17"], 1, inf)
        assert len(inf.errores) == 3
        assert all("2026-08-19" in e and "2026-08-17" not in e for e in inf.errores)

    def test_detecta_datos_antiguos(self, conn):
        _snapshots(conn, ["2026-08-16", "2026-08-17"])
        inf = Informe()
        check_continuidad(conn, T, date(2026, 8, 20), [], 1, inf)
        assert any("3 días sin datos" in e for e in inf.errores)

    def test_todo_correcto(self, conn):
        _snapshots(conn, ["2026-08-19", "2026-08-20"])
        inf = Informe()
        check_continuidad(conn, T, date(2026, 8, 20), [], 1, inf)
        assert not inf.errores and len(inf.ok) == 3


def _partido(id_, jornada, loc, vis, estado="played", fecha="2026-08-20"):
    return {"id_partido": id_, "jornada": jornada, "id_local": loc, "id_visitante": vis,
            "local": f"E{loc}", "visitante": f"E{vis}", "estado": estado, "fecha": fecha, "hora": "21:00"}


class TestGameweekVsCalendario:
    def test_partido_jugado_sin_datos_es_error_y_aplazado_es_aviso(self, conn):
        _tabla(conn, "calendario", [{"id_gameweek": 1, "jornada": 1, "estado": "ongoing"}])
        _tabla(conn, "partidos", [
            _partido(1, 1, 15, 3), _partido(2, 1, 7, 8), _partido(3, 1, 12, 1, "fixture", "2026-10-21"),
        ])
        _tabla(conn, "gameweek", [{"Jornada": 1, "EquipoLocal": 15, "EquipoVisitante": 3,
                                   "Manager": "A", "NombreJugador": "X"}])
        inf = Informe()
        check_gameweek_vs_calendario(conn, T, inf)
        assert len(inf.errores) == 1 and "E7–E8" in inf.errores[0]
        assert len(inf.avisos) == 1 and "E12–E1" in inf.avisos[0]

    def test_sin_partidos_solo_avisa(self, conn):
        inf = Informe()
        check_gameweek_vs_calendario(conn, T, inf)
        assert not inf.errores and inf.avisos


class TestClasificaciones:
    def test_jornada_terminada_ausente_o_incompleta(self, conn):
        _tabla(conn, "calendario", [{"id_gameweek": i, "jornada": i, "estado": "finished"} for i in (1, 2, 3)])
        _tabla(conn, "clasificaciones", [{"jornada": 1, "nombre": n} for n in "ABC"]
               + [{"jornada": 2, "nombre": n} for n in "AB"])
        inf = Informe()
        check_clasificaciones(conn, T, inf)
        assert any("J3" in e for e in inf.errores)
        assert any("J2 (2/3)" in e for e in inf.errores)


class TestDuplicadosYEncogimiento:
    def test_duplicados_por_clave(self, conn):
        _tabla(conn, "clasificaciones", [{"jornada": 1, "nombre": "A", "puntos": 1},
                                         {"jornada": 1, "nombre": "A", "puntos": 2}])
        inf = Informe()
        check_duplicados(conn, T, inf)
        assert inf.errores and "clasificaciones" in inf.errores[0]

    def test_tabla_que_pierde_filas(self, conn, tmp_path):
        base = tmp_path / "antes.db"
        with sqlite3.connect(base) as b:
            _tabla(b, "mercado", [{"date": "2026-08-20"}] * 3)
        _tabla(conn, "mercado", [{"date": "2026-08-20"}])
        inf = Informe()
        check_encogimiento(conn, base, T, inf)
        assert inf.errores and "3 → 1" in inf.errores[0]
