"""
Tests para scripts/regenerate_app_data.py — en particular el contrato de
nombres de fichero entre run_newspaper.py y build_news() (hallazgo IA-01):
antes, run_newspaper.py nombraba las ediciones por fecha de ejecución y
build_news() las buscaba por jornada, así que nunca coincidían y ningún
artículo nuevo aparecía en la web.
"""
import json
from pathlib import Path


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
