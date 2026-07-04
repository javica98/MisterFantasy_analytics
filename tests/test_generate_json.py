"""
Tests unitarios para src/AI_newspaper/generate_json.py
Cubre: map_team, map_position, clasificacion_dict,
       generate_json, generate_json_for_jornada
"""
import pandas as pd
import pytest

from src.AI_newspaper.generate_json import (
    clasificacion_dict,
    generate_json,
    generate_json_for_jornada,
)
from src.utils.team_map import TEAM_MAP, TEAM_POSICION, map_position, map_team


# ─────────────────────────────────────────────
# map_team
# ─────────────────────────────────────────────

class TestMapTeam:
    def test_id_entero_conocido(self):
        assert map_team(15) == "Real Madrid"

    def test_id_float_conocido(self):
        """equipoLiga llega como float desde el CSV — debe funcionar igual."""
        assert map_team(15.0) == "Real Madrid"
        assert map_team(3.0) == "FC Barcelona"

    def test_id_desconocido_devuelve_el_mismo(self):
        assert map_team(9999) == 9999

    def test_todos_los_ids_del_mapa_resuelven(self):
        for team_id, name in TEAM_MAP.items():
            assert map_team(team_id) == name

    def test_id_none_devuelve_sin_equipo(self):
        assert map_team(None) == "Sin equipo"

    def test_id_cero_devuelve_sin_equipo(self):
        assert map_team(0) == "Sin equipo"
        assert map_team(0.0) == "Sin equipo"


# ─────────────────────────────────────────────
# map_position
# ─────────────────────────────────────────────

class TestMapPosition:
    def test_posicion_1_es_portero(self):
        assert map_position(1) == "Portero"

    def test_posicion_4_es_delantero(self):
        assert map_position(4) == "Delantero"

    def test_posicion_desconocida_devuelve_la_misma(self):
        assert map_position(99) == 99

    def test_todas_las_posiciones_del_mapa(self):
        for pos_id, name in TEAM_POSICION.items():
            assert map_position(pos_id) == name


# ─────────────────────────────────────────────
# clasificacion_dict
# ─────────────────────────────────────────────

class TestClasificacionDict:
    def test_estructura_de_salida(self, df_clasificacion):
        result = clasificacion_dict(df_clasificacion)
        assert isinstance(result, dict)
        assert "Maldinillo" in result
        assert "puntos" in result["Maldinillo"]
        assert "posicion" in result["Maldinillo"]

    def test_orden_por_puntos(self, df_clasificacion):
        result = clasificacion_dict(df_clasificacion)
        assert result["Maldinillo"]["posicion"] == 1
        assert result["Dani"]["posicion"] == 2
        assert result["Los marinero"]["posicion"] == 3

    def test_df_vacio(self):
        df = pd.DataFrame(columns=["nombre", "puntos"])
        result = clasificacion_dict(df)
        assert result == {}

    def test_acumula_puntos_de_varias_jornadas(self):
        df = pd.DataFrame([
            {"nombre": "Maldinillo", "puntos": 60},
            {"nombre": "Maldinillo", "puntos": 60},
            {"nombre": "Dani",       "puntos": 100},
        ])
        result = clasificacion_dict(df)
        assert result["Maldinillo"]["puntos"] == 120
        assert result["Dani"]["puntos"] == 100
        assert result["Maldinillo"]["posicion"] == 1  # 120 > 100


# ─────────────────────────────────────────────
# generate_json
# ─────────────────────────────────────────────

class TestGenerateJson:
    def test_estructura_de_salida(self, df_transfers, df_gameweek, df_clasificacion, df_quinielas):
        result = generate_json(30, df_transfers, df_gameweek, df_clasificacion, df_quinielas)
        assert "transfers" in result
        assert "gameweek" in result
        assert "clasificacion" in result
        assert "quinielas" in result
        assert "fecha_inicio" in result
        assert "fecha_fin" in result

    def test_transfers_tienen_campos_requeridos(self, df_transfers, df_gameweek, df_clasificacion, df_quinielas):
        result = generate_json(30, df_transfers, df_gameweek, df_clasificacion, df_quinielas)
        for t in result["transfers"]:
            assert "jugador" in t
            assert "equipo" in t
            assert "equipo_jugador" in t
            assert "ganancias" in t
            assert "compra_venta" in t
            assert "clasificacion_manager_general" in t
            assert "clasificacion_manager_jornada" in t

    def test_equipo_jugador_resuelto(self, df_transfers, df_gameweek, df_clasificacion, df_quinielas):
        """equipoLiga numérico debe resolverse a nombre de equipo."""
        result = generate_json(30, df_transfers, df_gameweek, df_clasificacion, df_quinielas)
        for t in result["transfers"]:
            # No debe ser un número
            assert not isinstance(t["equipo_jugador"], (int, float)), \
                f"equipo_jugador sin resolver: {t['equipo_jugador']}"

    def test_gameweek_tiene_campos_requeridos(self, df_transfers, df_gameweek, df_clasificacion, df_quinielas):
        result = generate_json(30, df_transfers, df_gameweek, df_clasificacion, df_quinielas)
        for g in result["gameweek"]:
            assert "jugador" in g
            assert "manager" in g
            assert "puntos" in g
            assert "equipo_jugador" in g
            assert "posicion" in g

    def test_posicion_resuelta_a_string(self, df_transfers, df_gameweek, df_clasificacion, df_quinielas):
        result = generate_json(30, df_transfers, df_gameweek, df_clasificacion, df_quinielas)
        for g in result["gameweek"]:
            assert isinstance(g["posicion"], str), \
                f"posicion no resuelta: {g['posicion']}"

    def test_jugadores_sin_nombre_excluidos(self, df_clasificacion, df_quinielas, df_gameweek):
        """Filas de transfer sin jugador no deben aparecer en el JSON."""
        df = pd.DataFrame([
            {"fecha": "2026-03-01", "type": "transfer", "subtype": "mercado",
             "equipo": "Maldinillo", "ganancias": -10.0,
             "jugador": None, "compra-venta": "compra", "equipoLiga": 15},
        ])
        result = generate_json(30, df, df_gameweek, df_clasificacion, df_quinielas)
        assert result["transfers"] == []

    def test_clasificacion_tiene_general_y_jornada(self, df_transfers, df_gameweek, df_clasificacion, df_quinielas):
        result = generate_json(30, df_transfers, df_gameweek, df_clasificacion, df_quinielas)
        assert "general" in result["clasificacion"]
        assert "jornada" in result["clasificacion"]


# ─────────────────────────────────────────────
# generate_json_for_jornada
# ─────────────────────────────────────────────

class TestGenerateJsonForJornada:
    def test_estructura_basica(self, df_transfers, df_gameweek, df_clasificacion, df_quinielas):
        from datetime import date
        result = generate_json_for_jornada(
            jornada_num=25,
            fecha_transfers_start=date(2026, 2, 28),
            fecha_jornada_end=date(2026, 3, 2),
            df_clean=df_transfers,
            df_gameweek=df_gameweek,
            df_clasificacion=df_clasificacion,
            df_quinielas=df_quinielas,
        )
        assert result["jornada"] == 25
        assert "transfers" in result
        assert "gameweek" in result
        assert "clasificacion" in result

    def test_solo_incluye_gameweek_de_la_jornada(self, df_transfers, df_gameweek, df_clasificacion, df_quinielas):
        from datetime import date
        # Añadimos una fila de otra jornada
        extra = df_gameweek.copy()
        extra["Jornada"] = 99
        df_combined = pd.concat([df_gameweek, extra], ignore_index=True)

        result = generate_json_for_jornada(
            jornada_num=25,
            fecha_transfers_start=date(2026, 2, 1),
            fecha_jornada_end=date(2026, 3, 31),
            df_clean=df_transfers,
            df_gameweek=df_combined,
            df_clasificacion=df_clasificacion,
            df_quinielas=df_quinielas,
        )
        for g in result["gameweek"]:
            assert g["jornada"] == 25

    def test_clasificacion_acumulada_hasta_jornada(self, df_transfers, df_gameweek, df_quinielas):
        from datetime import date
        df_clas = pd.DataFrame([
            {"nombre": "Maldinillo", "puntos": 60, "jornada": 24},
            {"nombre": "Maldinillo", "puntos": 60, "jornada": 25},
            {"nombre": "Dani",       "puntos": 100, "jornada": 26},  # futura, NO debe incluirse
        ])
        result = generate_json_for_jornada(
            jornada_num=25,
            fecha_transfers_start=date(2026, 2, 1),
            fecha_jornada_end=date(2026, 3, 31),
            df_clean=df_transfers,
            df_gameweek=df_gameweek,
            df_clasificacion=df_clas,
            df_quinielas=df_quinielas,
        )
        # Maldinillo debe tener 120 puntos (j24 + j25), Dani no debe aparecer
        general = result["clasificacion"]["general"]
        assert general["Maldinillo"]["puntos"] == 120
        assert "Dani" not in general
