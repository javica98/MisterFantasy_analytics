"""
Tests para scripts/regenerate_app_data.py — en particular el contrato de
nombres de fichero entre run_newspaper.py y build_news() (hallazgo IA-01):
antes, run_newspaper.py nombraba las ediciones por fecha de ejecución y
build_news() las buscaba por jornada, así que nunca coincidían y ningún
artículo nuevo aparecía en la web.
"""
import json
from pathlib import Path

import pandas as pd
from PIL import Image

from scripts import regenerate_app_data as rad
from scripts.regenerate_app_data import build_news, _load_standings_snapshot


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestBuildNews:
    def test_encuentra_una_edicion_nombrada_por_jornada(self, tmp_path):
        events = {
            "fecha_inicio": "2026-08-17", "fecha_fin": "2026-08-20",
            "transfers": [], "gameweek": [],
            "clasificacion": {"general": {"Dani": {"puntos": 10, "posicion": 1}}, "jornada": {}},
            "quinielas": {"general": {}, "jornada": {}},
        }
        cards = {"cards": [{"tipo": "clasificacion", "titulo": "Título", "subtitulo": "Sub", "texto": ["Frase"]}]}
        _write_json(tmp_path / "articles" / "jornada_5_json.json", events)
        _write_json(tmp_path / "cards" / "jornada_5_cards.json", cards)

        news = build_news(tmp_path)

        assert len(news) == 1
        assert news[0]["date"] == "J5"
        assert news[0]["title"] == "Título"

    def test_ignora_articles_sin_cards_correspondientes(self, tmp_path):
        events = {"clasificacion": {"general": {}}, "quinielas": {}}
        _write_json(tmp_path / "articles" / "jornada_7_json.json", events)
        # sin cards/jornada_7_cards.json -> no debe indexarse

        assert build_news(tmp_path) == []

    def test_un_nombre_de_fichero_por_fecha_no_se_indexa(self, tmp_path):
        # Reproduce el bug real anterior a IA-01: guardar por fecha en vez
        # de por jornada hace que build_news() no encuentre nada.
        events = {"clasificacion": {"general": {}}, "quinielas": {}}
        cards = {"cards": [{"tipo": "clasificacion", "titulo": "T", "subtitulo": "S", "texto": ["x"]}]}
        _write_json(tmp_path / "articles" / "2026-08-20_json.json", events)
        _write_json(tmp_path / "cards" / "news_cards.json", cards)

        assert build_news(tmp_path) == []


class TestLoadStandingsSnapshot:
    def test_extrae_clasificacion_general_del_articulo(self, tmp_path):
        events = {
            "clasificacion": {
                "general": {
                    "Dani": {"puntos": 20, "posicion": 1},
                    "Maldinillo": {"puntos": 15, "posicion": 2},
                }
            }
        }
        f = tmp_path / "jornada_5_json.json"
        _write_json(f, events)

        snapshot = _load_standings_snapshot(f)

        assert len(snapshot) == 2
        assert snapshot[0]["manager"] == "Dani"
        assert snapshot[0]["rank"] == 1


def _gameweek(rows):
    """rows: (jornada, manager, puntos, equipo, posicion)"""
    return pd.DataFrame([
        {"Jornada": j, "Manager": m, "Puntos": p, "NombreJugador": f"Jugador {m}",
         "EquipoJugador": eq, "Posicion": pos, "Goles": 0, "Asistencias": 0,
         "Roja": 0, "Date": f"2026-08-{10 + j:02d}"}
        for j, m, p, eq, pos in rows
    ])


_EMPTY_TRANSFERS = pd.DataFrame(columns=["equipo", "compra-venta", "subtype", "ganancias", "jugador", "fecha"])


class TestSeasonForm:
    def test_jornada_ausente_va_como_null_sin_desplazar_las_siguientes(self):
        # Falta la J2 en la BD: antes seasonForm se compactaba a [10, 30] y la
        # web etiquetaba la J3 como "Jornada 2".
        df = _gameweek([(1, "Dani", 10, 15, 4), (3, "Dani", 30, 15, 4)])
        standings = [{"rank": 1, "manager": "Dani", "points": 40}]

        managers = rad.build_managers(df, None, _EMPTY_TRANSFERS, standings)

        assert managers[0]["seasonForm"] == [10, None, 30]

    def test_posicion_y_equipo_se_traducen_a_nombre(self):
        df = _gameweek([(1, "Dani", 10, 1490, 4.0)])
        standings = [{"rank": 1, "manager": "Dani", "points": 10}]

        best = rad.build_managers(df, None, _EMPTY_TRANSFERS, standings)[0]["bestPlayer"]

        assert best["team"] == "Racing de Santander"
        assert best["position"] == "Delantero"


class TestPlayerOfMonth:
    def test_equipo_se_traduce_a_nombre_y_no_queda_el_id(self):
        # Antes salía "team": "9" en la home.
        df = _gameweek([(1, "Dani", 14, 9, 3)])
        standings = [{"rank": 1, "manager": "Dani", "points": 14}]

        league = rad.build_league(df, None, _EMPTY_TRANSFERS, standings, [], [])

        assert league["playerOfMonth"]["team"] == "Getafe CF"
        assert league["lastRound"] == 1


class TestCoverThumbnails:
    def test_genera_miniatura_webp_y_la_enlaza_en_la_edicion(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rad, "COVERS_DIR", tmp_path / "covers")
        src_dir = tmp_path / "new"
        src_dir.mkdir()
        Image.new("RGB", (1080, 1350), "white").save(src_dir / "jornada_5_jornada_news.png")
        cards = {"cards": [{"tipo": "clasificacion", "titulo": "T", "subtitulo": "S", "texto": ["x"]}]}
        _write_json(tmp_path / "json" / "articles" / "jornada_5_json.json", {"clasificacion": {}})
        _write_json(tmp_path / "json" / "cards" / "jornada_5_cards.json", cards)

        news = build_news(tmp_path / "json", src_dir, "2026-27")

        assert news[0]["cover"] == "/web/covers/2026-27/jornada_5.webp"
        with Image.open(tmp_path / "covers" / "2026-27" / "jornada_5.webp") as thumb:
            assert thumb.format == "WEBP"
            assert thumb.size == (rad.COVER_WIDTH, 300)

    def test_sin_portada_original_no_hay_cover(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rad, "COVERS_DIR", tmp_path / "covers")
        cards = {"cards": [{"tipo": "clasificacion", "titulo": "T", "subtitulo": "S", "texto": ["x"]}]}
        _write_json(tmp_path / "json" / "articles" / "jornada_2_json.json", {"clasificacion": {}})
        _write_json(tmp_path / "json" / "cards" / "jornada_2_cards.json", cards)

        news = build_news(tmp_path / "json", tmp_path / "new", "2026-27")

        assert news[0]["cover"] is None
