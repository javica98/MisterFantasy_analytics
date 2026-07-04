"""
Tests unitarios para src/AI_newspaper/generate_prompt.py
Cubre: get_top_signings, get_top_sale, get_mvps, get_worst_player,
       get_red_cards, get_penalty_saves, get_own_goals,
       build_player_block, generate_prompts, build_final_prompt
"""
import pytest

from src.AI_newspaper.generate_prompt import (
    build_final_prompt,
    build_player_block,
    generate_prompts,
    get_mvps,
    get_own_goals,
    get_penalty_saves,
    get_red_cards,
    get_top_sale,
    get_top_signings,
    get_worst_player,
)


# ─────────────────────────────────────────────
# Datos de ejemplo
# ─────────────────────────────────────────────

TRANSFERS = [
    {"jugador": "Mbappé",   "equipo": "Maldinillo", "equipo_jugador": "Real Madrid",
     "subtype": "clausula", "ganancias": -131.4, "compra_venta": "compra",
     "clasificacion_manager_general": {"posicion": 1, "puntos": 120},
     "clasificacion_manager_jornada": {"posicion": 2, "puntos": 60}},
    {"jugador": "Raphinha",  "equipo": "Dani",       "equipo_jugador": "FC Barcelona",
     "subtype": "mercado",  "ganancias": 20.0,   "compra_venta": "venta",
     "clasificacion_manager_general": {"posicion": 2, "puntos": 115},
     "clasificacion_manager_jornada": {"posicion": 1, "puntos": 70}},
    {"jugador": "T. Lemar",  "equipo": "Los marinero", "equipo_jugador": "Atlético de Madrid",
     "subtype": "mercado",  "ganancias": -8.0,   "compra_venta": "compra",
     "clasificacion_manager_general": {"posicion": 3, "puntos": 90},
     "clasificacion_manager_jornada": {"posicion": 3, "puntos": 40}},
]

GAMEWEEK = [
    {"jugador": "Mbappé", "manager": "Maldinillo", "equipo_jugador": "Real Madrid",
     "puntos": 18, "roja": 0, "penalti_parado": 0, "gol_propia": 0,
     "clasificacion_manager_general": {"posicion": 1, "puntos": 120},
     "clasificacion_manager_jornada": {"posicion": 2, "puntos": 60}},
    {"jugador": "Raphinha", "manager": "Dani", "equipo_jugador": "FC Barcelona",
     "puntos": 12, "roja": 0, "penalti_parado": 0, "gol_propia": 0,
     "clasificacion_manager_general": {"posicion": 2, "puntos": 115},
     "clasificacion_manager_jornada": {"posicion": 1, "puntos": 70}},
    {"jugador": "T. Lemar", "manager": "Los marinero", "equipo_jugador": "Atlético de Madrid",
     "puntos": 2, "roja": 0, "penalti_parado": 0, "gol_propia": 0,
     "clasificacion_manager_general": {"posicion": 3, "puntos": 90},
     "clasificacion_manager_jornada": {"posicion": 3, "puntos": 40}},
]


# ─────────────────────────────────────────────
# get_top_signings
# ─────────────────────────────────────────────

class TestGetTopSignings:
    def test_solo_devuelve_compras(self):
        result = get_top_signings(TRANSFERS, top_n=5)
        for t in result:
            assert t["compra_venta"] == "compra"

    def test_respeta_top_n(self):
        result = get_top_signings(TRANSFERS, top_n=1)
        assert len(result) <= 1

    def test_lista_vacia(self):
        assert get_top_signings([], top_n=3) == []

    def test_solo_ventas_devuelve_vacio(self):
        ventas = [t for t in TRANSFERS if t["compra_venta"] == "venta"]
        assert get_top_signings(ventas, top_n=3) == []


# ─────────────────────────────────────────────
# get_top_sale
# ─────────────────────────────────────────────

class TestGetTopSale:
    def test_devuelve_la_mayor_venta_de_mercado(self):
        result = get_top_sale(TRANSFERS)
        assert result is not None
        assert result["compra_venta"] == "venta"
        assert result["subtype"] == "mercado"

    def test_lista_vacia_devuelve_none(self):
        assert get_top_sale([]) is None

    def test_sin_mercado_devuelve_none(self):
        solo_clausulas = [t for t in TRANSFERS if t["subtype"] == "clausula"]
        assert get_top_sale(solo_clausulas) is None


# ─────────────────────────────────────────────
# get_mvps
# ─────────────────────────────────────────────

class TestGetMvps:
    def test_primero_es_el_de_mas_puntos(self):
        result = get_mvps(GAMEWEEK, top_n=3)
        assert result[0]["puntos"] == 18

    def test_respeta_top_n(self):
        result = get_mvps(GAMEWEEK, top_n=2)
        assert len(result) == 2

    def test_lista_vacia(self):
        assert get_mvps([], top_n=3) == []


# ─────────────────────────────────────────────
# get_worst_player
# ─────────────────────────────────────────────

class TestGetWorstPlayer:
    def test_devuelve_el_de_menos_puntos(self):
        result = get_worst_player(GAMEWEEK)
        assert result["puntos"] == 2

    def test_lista_vacia_devuelve_none(self):
        assert get_worst_player([]) is None


# ─────────────────────────────────────────────
# get_red_cards
# ─────────────────────────────────────────────

class TestGetRedCards:
    def test_sin_rojas_devuelve_none(self):
        assert get_red_cards(GAMEWEEK) is None

    def test_devuelve_jugador_con_roja(self):
        gw = GAMEWEEK.copy()
        gw[0] = {**gw[0], "roja": 1}
        result = get_red_cards(gw)
        assert result is not None
        assert result["roja"] == 1

    def test_lista_vacia_devuelve_none(self):
        assert get_red_cards([]) is None


# ─────────────────────────────────────────────
# get_penalty_saves
# ─────────────────────────────────────────────

class TestGetPenaltySaves:
    def test_sin_penaltis_parados_devuelve_none(self):
        assert get_penalty_saves(GAMEWEEK) is None

    def test_devuelve_jugador_con_penalti_parado(self):
        gw = GAMEWEEK.copy()
        gw[1] = {**gw[1], "penalti_parado": 1}
        result = get_penalty_saves(gw)
        assert result is not None
        assert result["penalti_parado"] == 1


# ─────────────────────────────────────────────
# get_own_goals
# ─────────────────────────────────────────────

class TestGetOwnGoals:
    def test_sin_goles_en_propia_devuelve_none(self):
        assert get_own_goals(GAMEWEEK) is None

    def test_devuelve_jugador_con_gol_propia(self):
        gw = GAMEWEEK.copy()
        gw[2] = {**gw[2], "gol_propia": 1}
        result = get_own_goals(gw)
        assert result is not None
        assert result["gol_propia"] == 1


# ─────────────────────────────────────────────
# build_player_block
# ─────────────────────────────────────────────

class TestBuildPlayerBlock:
    def test_estructura_de_salida(self):
        block = build_player_block("Mbappé", "Maldinillo", "Real Madrid", "MVP de la jornada", "contexto", 18, None)
        assert block["jugador"] == "Mbappé"
        assert block["manager"] == "Maldinillo"
        assert block["equipo"] == "Real Madrid"
        assert block["evento"] == "MVP de la jornada"
        assert block["puntos"] == 18
        assert block["dinero"] is None

    def test_campos_opcionales_none(self):
        block = build_player_block("X", "Y", "Z", "evento", "ctx", None, None)
        assert block["puntos"] is None
        assert block["dinero"] is None


# ─────────────────────────────────────────────
# generate_prompts
# ─────────────────────────────────────────────

class TestGeneratePrompts:
    def test_devuelve_bloques_lista(self, sample_events_json):
        result = generate_prompts(sample_events_json)
        assert "bloques" in result
        assert isinstance(result["bloques"], list)
        assert len(result["bloques"]) > 0

    def test_bloques_tienen_campos_requeridos(self, sample_events_json):
        result = generate_prompts(sample_events_json)
        for bloque in result["bloques"]:
            assert "jugador" in bloque
            assert "manager" in bloque
            assert "equipo" in bloque
            assert "evento" in bloque

    def test_hay_mvp(self, sample_events_json):
        result = generate_prompts(sample_events_json)
        tipos = [b["evento"] for b in result["bloques"]]
        assert "MVP de la jornada" in tipos

    def test_hay_fichaje(self, sample_events_json):
        result = generate_prompts(sample_events_json)
        tipos = [b["evento"] for b in result["bloques"]]
        assert "Fichaje destacado" in tipos

    def test_jugadores_mencionados_es_lista(self, sample_events_json):
        result = generate_prompts(sample_events_json)
        assert isinstance(result["jugadores_mencionados"], list)

    def test_sin_datos_devuelve_lista_vacia(self):
        result = generate_prompts({"transfers": [], "gameweek": []})
        assert result["bloques"] == []

    def test_no_duplica_jugadores_mencionados(self, sample_events_json):
        result = generate_prompts(sample_events_json)
        mencionados = result["jugadores_mencionados"]
        assert len(mencionados) == len(set(mencionados))


# ─────────────────────────────────────────────
# build_final_prompt
# ─────────────────────────────────────────────

class TestBuildFinalPrompt:
    def test_devuelve_string(self, sample_events_json):
        from src.AI_newspaper.generate_prompt import generate_prompts
        prompts = generate_prompts(sample_events_json)
        result = build_final_prompt(prompts["bloques"], sample_events_json, "")
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contiene_instruccion_json(self, sample_events_json):
        from src.AI_newspaper.generate_prompt import generate_prompts
        prompts = generate_prompts(sample_events_json)
        result = build_final_prompt(prompts["bloques"], sample_events_json, "")
        assert "cards" in result
        assert "JSON" in result

    def test_incluye_memoria_si_se_pasa(self, sample_events_json):
        from src.AI_newspaper.generate_prompt import generate_prompts
        prompts = generate_prompts(sample_events_json)
        memoria = "Maldinillo ganó la jornada 20."
        result = build_final_prompt(prompts["bloques"], sample_events_json, memoria)
        assert memoria in result

    def test_incluye_datos_de_jugadores(self, sample_events_json):
        from src.AI_newspaper.generate_prompt import generate_prompts
        prompts = generate_prompts(sample_events_json)
        result = build_final_prompt(prompts["bloques"], sample_events_json, "")
        # Al menos uno de los jugadores del fixture debe aparecer
        assert any(j in result for j in ["Mbappé", "Raphinha", "Lemar"])
