"""
Tests del calendario de jornadas (/ajax/sw/gameweek), la selección de
jornadas a re-scrapear y los merges que dependen de ellos.

Datos sintéticos: el repo es público, no se usan respuestas reales de la liga.
"""
from datetime import date

import pandas as pd

from src.data.extract_calendario import (
    anotar_fecha_partido, merge_partidos, parse_calendario, parse_partidos, seleccionar_jornadas,
)
from src.data.merge_clasification import merge_clasifications
from src.data.merge_gameweek import merge_gameweek
from src.data.merge_quinielas import merge_quinielas


def _gw(id_, n, status, first, last):
    return {"id": id_, "gameweek": n, "type": "regular", "status": status,
            "firstMatchDate": first, "lastMatchDate": last}


CALENDARIO = {"status": "ok", "data": {"gameweeks": [
    _gw(100, 1, "finished", "2026-08-15 19:30:00", "2026-08-17 21:00:00"),
    _gw(101, 2, "ongoing", "2026-08-22 19:00:00", "2026-10-21 20:00:00"),  # con aplazado
    _gw(102, 3, "finished", "2026-09-28 19:00:00", "2026-10-01 21:00:00"),
    _gw(103, 4, "unstarted", "2026-10-09 21:00:00", "2026-10-12 21:00:00"),
]}}

JORNADA_2 = {"status": "ok", "data": {
    "gameweekStatus": {"id": 101, "gameweek": 2, "status": "ongoing"},
    "games": [
        # 2026-08-22 19:00 UTC = 21:00 en Madrid
        {"id": 1, "id_gameweek": 101, "id_home": 15, "id_away": 3, "goals_home": 2, "goals_away": 1,
         "status": "played", "date": {"ts": 1787425200}, "home": "Real Madrid", "away": "Barça"},
        # Aplazado: 2026-10-21 18:00 UTC = 20:00 en Madrid
        {"id": 2, "id_gameweek": 101, "id_home": 12, "id_away": 1, "goals_home": "-", "goals_away": "-",
         "status": "fixture", "date": {"ts": 1792605600}, "home": "Levante", "away": "Athletic Club"},
    ],
}}


def _fila_gw(jornada, local, visit, manager, jugador, puntos, fecha="2026-10-07"):
    return {"Date": fecha, "Jornada": jornada, "EquipoLocal": local, "EquipoVisitante": visit,
            "Manager": manager, "NombreJugador": jugador, "Puntos": puntos}


class TestParseCalendario:
    def test_extrae_todas_las_jornadas_con_estado(self):
        df = parse_calendario(CALENDARIO)
        assert list(df["jornada"]) == [1, 2, 3, 4]
        assert list(df["estado"]) == ["finished", "ongoing", "finished", "unstarted"]
        assert df.loc[df["jornada"] == 2, "ultimo_partido"].item() == "2026-10-21 20:00:00"

    def test_payload_vacio_devuelve_df_con_columnas(self):
        df = parse_calendario({})
        assert df.empty and "id_gameweek" in df.columns


class TestParsePartidos:
    def test_fecha_en_hora_de_madrid_y_goles_de_aplazado_nulos(self):
        df = parse_partidos(JORNADA_2)
        jugado = df[df["id_partido"] == 1].iloc[0]
        aplazado = df[df["id_partido"] == 2].iloc[0]
        assert (jugado["jornada"], jugado["fecha"], jugado["hora"]) == (2, "2026-08-22", "21:00")
        assert (jugado["goles_local"], jugado["goles_visitante"]) == (2, 1)
        assert aplazado["estado"] == "fixture" and aplazado["fecha"] == "2026-10-21"
        assert pd.isna(aplazado["goles_local"])

    def test_merge_partidos_actualiza_el_aplazado_al_jugarse(self):
        viejo = parse_partidos(JORNADA_2)
        jugado = {**JORNADA_2["data"]["games"][1], "status": "played", "goals_home": 1, "goals_away": 1}
        nuevo = parse_partidos({"data": {**JORNADA_2["data"], "games": [jugado]}})
        df = merge_partidos(viejo, nuevo)
        assert len(df) == 2
        assert df.loc[df["id_partido"] == 2, "estado"].item() == "played"


class TestSeleccionarJornadas:
    def test_primera_ejecucion_pide_todas_las_no_futuras(self):
        ids = seleccionar_jornadas(parse_calendario(CALENDARIO), set(), hoy=date(2026, 10, 7))
        assert ids == [100, 101, 102]

    def test_luego_solo_ongoing_y_recientes(self):
        ids = seleccionar_jornadas(parse_calendario(CALENDARIO), {1, 2, 3}, hoy=date(2026, 10, 7))
        # J1 acabó hace >7 días y ya está descargada; J3 acabó hace 6 días.
        assert ids == [101, 102]

    def test_jornada_reciente_deja_de_pedirse_tras_la_ventana(self):
        ids = seleccionar_jornadas(parse_calendario(CALENDARIO), {1, 2, 3}, hoy=date(2026, 10, 9))
        assert ids == [101]

    def test_calendario_vacio(self):
        assert seleccionar_jornadas(pd.DataFrame(), set()) == []


class TestAnotarFechaPartido:
    def test_sustituye_date_por_fecha_real_y_conserva_si_no_hay_partido(self):
        gw = pd.DataFrame([_fila_gw(2, 15, 3, "Dani", "Vini", 10), _fila_gw(2, 9, 9, "Dani", "X", 1)])
        out = anotar_fecha_partido(gw, parse_partidos(JORNADA_2))
        assert list(out["Date"]) == ["2026-08-22", "2026-10-07"]


class TestMergeGameweekUpsert:
    def test_corrige_puntos_y_anade_partidos_nuevos(self):
        viejo = pd.DataFrame([
            _fila_gw(1, 15, 3, "Dani", "Vini", 8),
            _fila_gw(1, 7, 8, "Juanba", "Pedri", 5),
        ])
        nuevo = pd.DataFrame([
            _fila_gw(1, 15, 3, "Dani", "Vini", 9),        # corrección de Mister
            _fila_gw(1, 15, 3, "Libre", "Bellingham", 6),  # fila que faltaba
            _fila_gw(1, 2, 4, "Dani", "Oyarzabal", 4),    # partido que faltaba
        ])
        df = merge_gameweek(viejo, nuevo)
        assert len(df) == 4
        assert df.loc[df["NombreJugador"] == "Vini", "Puntos"].item() == 9
        assert df.loc[df["NombreJugador"] == "Pedri", "Puntos"].item() == 5  # partido no tocado

    def test_viejo_vacio_devuelve_nuevo(self):
        nuevo = pd.DataFrame([_fila_gw(1, 15, 3, "Dani", "Vini", 9)])
        assert len(merge_gameweek(pd.DataFrame(), nuevo)) == 1

    def test_nuevo_vacio_conserva_viejo(self):
        viejo = pd.DataFrame([_fila_gw(1, 15, 3, "Dani", "Vini", 9)])
        assert len(merge_gameweek(viejo, pd.DataFrame())) == 1


class TestMergesConTablaVacia:
    """La J1 de 2026-27 se perdió porque la tabla vieja vacía (sin columnas)
    hacía fallar el merge y se guardaba vacío."""

    NUEVO = pd.DataFrame([{"jornada": 1, "nombre": "Dani", "posicion": 1, "puntos": 30}])

    def test_clasificaciones_con_viejo_sin_columnas(self):
        assert len(merge_clasifications(pd.DataFrame(), self.NUEVO)) == 1

    def test_quinielas_con_viejo_sin_columnas(self):
        assert len(merge_quinielas(pd.DataFrame(), self.NUEVO)) == 1

    def test_clasificaciones_reemplaza_jornada(self):
        viejo = pd.DataFrame([{"jornada": 1, "nombre": "Dani", "posicion": 1, "puntos": 31}])
        df = merge_clasifications(viejo, self.NUEVO)
        assert len(df) == 1 and df["puntos"].item() == 30
