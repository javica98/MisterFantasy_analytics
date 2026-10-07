"""
Tests del feed en JSON (equivalencia con el extractor HTML), de los datos
extra del JSON de jornada (stats, once ideal, alineaciones) y del esquema
ampliable de la BD. Datos sintéticos: el repo es público.
"""
import json
import sqlite3

import pandas as pd

from src.data.extract_calendario import parse_alineaciones, parse_once_ideal, parse_stats_partidos, upsert
from src.data.extract_feed_json import cards_de_respuestas, extraer_feed_json
from src.data.extract_notificaciones import extraer_notificaciones, generar_id_transfer
from src.data.merge_notifications import merge_feed_cards_until_match
from src.utils import db as db_utils


def _transfer(name, frm, to, price, tipo="normal", other_bids=None):
    return {"type": tipo, "name": name, "from": frm, "to": to, "price": price, "position": 4,
            "points": 53, "id_team": 50, "other_bids": other_bids}


FEED = [
    {"id": 3, "category": "transfer", "created": "2026-10-02 13:39:55", "data": [
        _transfer("Ante Budimir", "Mister", "Dani", 17105210,
                  other_bids=[{"name": "Libre", "bid": 16000000}]),
        _transfer("Aitor Fernández", "Libre", "Juanba", 1579500, tipo="clause"),
    ]},
    {"id": 2, "category": "gameweek_end_pools", "created": "2026-09-21 11:16:45", "data": {"table": [
        {"name": "Dani", "hits": 6, "amount": 600000}, {"name": "Libre", "hits": 0, "amount": None},
    ]}},
    {"id": 1, "category": "gameweek_end", "created": "2026-09-21 11:16:09", "data": {"ranking": {"ranking": {
        "positions": [{"rank": 1, "points": 63, "payment": 2010000, "user": {"name": "Dani"}}]}}}},
    {"id": 0, "category": "gameweek_start", "created": "2026-09-16 21:34:19", "data": {"gameweek": 7}},
    {"id": -1, "category": "post", "created": "2026-09-15 10:00:00", "data": {}},
]

# El mismo traspaso de mercado tal como lo pinta la web.
FEED_HTML = """
<div class="feed-cards"><div class="card-wrapper">
  <div class="head"><div class="title">Nuevas transacciones en el mercado</div></div>
  <div class="card card-transfer"><ul class="player-list player-list--secondary"><li>
    <div class="title"><strong>Ante Budimir</strong> de <em>Mister</em> a <em>Dani</em></div>
    <div class="price">17.105.210</div>
    <div class="player-position" data-position="4"></div><div class="points">53</div>
    <div class="icons"><img class="team-logo" src="/teams/50.png"></div>
  </li></ul></div>
</div></div>
"""


class TestFeedJson:
    def test_filas_en_el_mismo_orden_que_el_html(self):
        df = extraer_feed_json(FEED)
        assert list(zip(df["type"], df["subtype"])) == [
            ("marks", "start_mercado"), ("transfer", "mercado"), ("transfer", "Puja"), ("transfer", "clausula"),
            ("bonificacion", "quiniela"), ("bonificacion", "quiniela"),
            ("bonificacion", "clasificacion"), ("marks", "start_jornada"),
        ]

    def test_id_transfer_identico_al_del_html(self):
        html = extraer_notificaciones(FEED_HTML)
        json_ = extraer_feed_json(FEED)
        assert html.loc[1, "idTransfer"] == json_.loc[1, "idTransfer"]
        assert json_.loc[2, "idTransfer"] == generar_id_transfer("Ante Budimir", "Mister", "Libre", "16.000.000")

    def test_fecha_real_y_campos_que_el_html_no_rellenaba(self):
        df = extraer_feed_json(FEED)
        assert df.loc[1, "date"] == "2026-10-02" and df.loc[1, "created"] == "2026-10-02 13:39:55"
        assert df.loc[1, "precio"] == 17.10521
        quiniela = df[df["subtype"] == "quiniela"]
        assert list(quiniela["position"]) == ["1º", "2º"] and list(quiniela["aciertos"]) == ["6", "0"]
        assert pd.isna(quiniela["money"].iloc[1])
        clasif = df[df["subtype"] == "clasificacion"].iloc[0]
        assert (clasif["points"], clasif["money"]) == ("63", 2.01)
        assert df[df["subtype"] == "start_jornada"]["jornada"].item() == 7

    def test_paginas_desordenadas_y_repetidas(self):
        pag = lambda off, ids: {"offset": off, "body": {"data": [{"id": i} for i in ids]}}  # noqa: E731
        cards = cards_de_respuestas([pag(20, [3, 4]), pag(0, [1, 2, 3])])
        assert [c["id"] for c in cards] == [1, 2, 3, 4]

    def test_merge_corta_en_lo_ya_guardado_y_conserva_la_fecha_real(self):
        nueva = {"id": 4, "category": "transfer", "created": "2026-10-05 09:00:00",
                 "data": [_transfer("Pedri", "Mister", "Libre", 30000000)]}
        viejo = extraer_feed_json(FEED)
        df = merge_feed_cards_until_match(viejo, extraer_feed_json([nueva] + FEED))
        assert len(df) == len(viejo) + 2  # marcador + traspaso nuevos, sin duplicar lo guardado
        assert list(df["date"].head(2)) == ["2026-10-05", "2026-10-05"]
        assert df.loc[3, "date"] == "2026-10-02"


GAMEWEEK = {"data": {
    "gameweekStatus": {"id": 4048, "gameweek": 7},
    "games": [{"id": 1, "stats": json.dumps([
        {"key": "expectedGoals", "name": "Expected goals", "home": "1.05", "away": "1.61",
         "homeValue": 1.05, "awayValue": 1.61},
        {"key": "expectedGoals", "name": "Expected goals", "home": "0.5", "away": "0.7",
         "homeValue": 0.5, "awayValue": 0.7},
    ])}, {"id": 2, "stats": None}],
    "best_lineup": {"selection": {"formation": "1-3-4-3", "score": 140, "marketValue": 87307000, "cards": [
        {"cardId": 7893, "cardName": "Antonio Sivera", "position": 1, "score": 10, "marketValue": 7581000,
         "teamId": 48}]}},
    "preview": {"37997": {"players": {"3": [{"id": 29166, "name": "Joan Garcia", "position": 1, "confirmed": 0}]}}},
}}


class TestDatosExtraJornada:
    def test_stats_una_fila_por_metrica_y_sin_partidos_sin_stats(self):
        df = parse_stats_partidos(GAMEWEEK)
        assert len(df) == 1
        assert (df["valor_local"].item(), df["valor_visitante"].item(), df["jornada"].item()) == (1.05, 1.61, 7)

    def test_once_ideal(self):
        df = parse_once_ideal(GAMEWEEK)
        fila = df.iloc[0]
        assert (fila["formacion"], fila["puntos_total"], fila["jugador"], fila["valor"]) == \
            ("1-3-4-3", 140, "Antonio Sivera", 7.581)

    def test_alineaciones(self):
        df = parse_alineaciones(GAMEWEEK)
        assert (df["id_partido"].item(), df["id_equipo"].item(), df["jugador"].item()) == (37997, 3, "Joan Garcia")

    def test_jornada_sin_jugar_no_trae_stats_ni_once(self):
        vacio = {"data": {"gameweekStatus": {"id": 4049, "gameweek": 8}, "games": [{"id": 3, "stats": None}]}}
        assert parse_stats_partidos(vacio).empty and parse_once_ideal(vacio).empty

    def test_upsert_sustituye_por_clave(self):
        viejo = pd.DataFrame({"jornada": [6, 7, 7], "orden": [1, 1, 2], "temporada": "2026-27"})
        nuevo = pd.DataFrame({"jornada": [7], "orden": [1]})
        df = upsert(viejo, nuevo, ["jornada"])
        assert sorted(zip(df["jornada"], df["orden"])) == [(6, 1), (7, 1)]


class TestEsquemaAmpliable:
    def test_write_table_anade_columnas_nuevas(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db_utils, "get_db_path", lambda: tmp_path / "t.db")
        db_utils.write_table(pd.DataFrame({"date": ["2026-10-06"]}), "mercado", "2026-27")
        ok = db_utils.write_table(
            pd.DataFrame({"date": ["2026-10-06", "2026-10-07"], "scraped_at": [None, "2026-10-07 13:00:00"]}),
            "mercado", "2026-27")
        assert ok
        with sqlite3.connect(tmp_path / "t.db") as c:
            cols = [r[1] for r in c.execute("PRAGMA table_info(mercado)")]
            assert "scraped_at" in cols
            assert c.execute("SELECT COUNT(*) FROM mercado").fetchone()[0] == 2
