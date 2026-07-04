"""
Tests unitarios para src/memory/embedding_store.py
Cubre: _load_cached_embeddings_by_id, build_memory_query,
       comportamiento incremental de rebuild_embedding_index
"""
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.memory.embedding_store import (
    _load_cached_embeddings_by_id,
    build_memory_query,
)


# ─────────────────────────────────────────────
# _load_cached_embeddings_by_id
# ─────────────────────────────────────────────

class TestLoadCachedEmbeddingsById:
    def _write_index(self, path: Path, items: list):
        index = {"items": items}
        with path.open("w", encoding="utf-8") as f:
            json.dump(index, f)

    def test_ficheros_inexistentes_devuelve_dict_vacio(self, tmp_path):
        result = _load_cached_embeddings_by_id(
            tmp_path / "no_existe.npy",
            tmp_path / "no_existe.json",
        )
        assert result == {}

    def test_carga_correctamente(self, tmp_path):
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"

        vecs = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        np.save(emb_path, vecs)
        self._write_index(idx_path, [
            {"id": "mem_001", "row": 0},
            {"id": "mem_002", "row": 1},
        ])

        result = _load_cached_embeddings_by_id(emb_path, idx_path)
        assert "mem_001" in result
        assert "mem_002" in result
        np.testing.assert_array_equal(result["mem_001"], [1.0, 0.0])
        np.testing.assert_array_equal(result["mem_002"], [0.0, 1.0])

    def test_row_fuera_de_rango_se_ignora(self, tmp_path):
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"

        vecs = np.array([[1.0, 0.0]], dtype=np.float32)  # solo 1 fila
        np.save(emb_path, vecs)
        self._write_index(idx_path, [
            {"id": "mem_001", "row": 0},
            {"id": "mem_999", "row": 99},  # row fuera de rango
        ])

        result = _load_cached_embeddings_by_id(emb_path, idx_path)
        assert "mem_001" in result
        assert "mem_999" not in result  # ignorado por row >= len

    def test_fichero_corrupto_devuelve_dict_vacio(self, tmp_path):
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"

        emb_path.write_bytes(b"esto no es numpy")
        idx_path.write_text("{}", encoding="utf-8")

        result = _load_cached_embeddings_by_id(emb_path, idx_path)
        assert result == {}

    def test_indice_sin_items_devuelve_dict_vacio(self, tmp_path):
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"

        np.save(emb_path, np.array([[1.0, 0.0]], dtype=np.float32))
        idx_path.write_text('{"model_name": "test"}', encoding="utf-8")

        result = _load_cached_embeddings_by_id(emb_path, idx_path)
        assert result == {}


# ─────────────────────────────────────────────
# build_memory_query
# ─────────────────────────────────────────────

class TestBuildMemoryQuery:
    def _make_events_json(self, transfers=None, gameweek=None, clasificacion=None):
        return {
            "transfers": transfers or [],
            "gameweek": gameweek or [],
            "clasificacion": clasificacion or {"general": {}, "jornada": {}},
        }

    def test_devuelve_string(self, sample_events_json):
        result = build_memory_query(sample_events_json)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_vacio_devuelve_string_vacio(self):
        result = build_memory_query(self._make_events_json())
        assert result == ""

    def test_incluye_datos_de_clasificacion(self):
        events = self._make_events_json(
            clasificacion={
                "general": {"Maldinillo": {"posicion": 1, "puntos": 120}},
                "jornada": {},
            }
        )
        result = build_memory_query(events)
        assert "Maldinillo" in result
        assert "120" in result

    def test_incluye_datos_de_transfers(self):
        events = self._make_events_json(
            transfers=[{
                "subtype": "clausula", "compra_venta": "compra",
                "equipo": "Maldinillo", "jugador": "Mbappé",
                "equipo_jugador": "Real Madrid", "ganancias": -131.4,
            }]
        )
        result = build_memory_query(events)
        assert "Mbappé" in result
        assert "Maldinillo" in result

    def test_incluye_datos_de_gameweek(self):
        events = self._make_events_json(
            gameweek=[{
                "manager": "Dani", "jugador": "Raphinha",
                "equipo_jugador": "FC Barcelona", "puntos": 18,
                "goles": 2, "asistencias": 1,
                "roja": 0, "gol_propia": 0,
                "penalti_parado": 0, "penalti_fallado": 0,
            }]
        )
        result = build_memory_query(events)
        assert "Raphinha" in result
        assert "Dani" in result

    def test_marca_roja_en_query(self):
        events = self._make_events_json(
            gameweek=[{
                "manager": "Maldinillo", "jugador": "Mbappé",
                "equipo_jugador": "Real Madrid", "puntos": 5,
                "goles": 0, "asistencias": 0,
                "roja": 1, "gol_propia": 0,
                "penalti_parado": 0, "penalti_fallado": 0,
            }]
        )
        result = build_memory_query(events)
        assert "roja" in result

    def test_penalti_parado_en_query(self):
        events = self._make_events_json(
            gameweek=[{
                "manager": "Dani", "jugador": "ter Stegen",
                "equipo_jugador": "FC Barcelona", "puntos": 12,
                "goles": 0, "asistencias": 0,
                "roja": 0, "gol_propia": 0,
                "penalti_parado": 1, "penalti_fallado": 0,
            }]
        )
        result = build_memory_query(events)
        assert "penalti parado" in result


# ─────────────────────────────────────────────
# rebuild_embedding_index — comportamiento incremental
# ─────────────────────────────────────────────

class TestRebuildEmbeddingIndexIncremental:
    """Verifica que el rebuild solo codifica memorias nuevas."""

    def _make_memory_file(self, tmp_path: Path, memories: list) -> Path:
        path = tmp_path / "memories.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for m in memories:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        return path

    def test_solo_codifica_memorias_nuevas(self, tmp_path, monkeypatch):
        from src.memory.embedding_store import rebuild_embedding_index

        # Primera memoria ya en caché
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"
        mem_path = self._make_memory_file(tmp_path, [
            {"id": "mem_001", "query_text": "Maldinillo ganó la jornada 20", "fecha": "2026-01-01",
             "category": "clasificacion", "manager": "Maldinillo", "player": None, "importance": 1,
             "summary": "test"},
            {"id": "mem_002", "query_text": "Mbappé marcó hat-trick", "fecha": "2026-01-02",
             "category": "jugador", "manager": "Maldinillo", "player": "Mbappé", "importance": 2,
             "summary": "test2"},
        ])

        # Precargamos el vector de mem_001
        vec_cached = np.array([0.5, 0.5], dtype=np.float32)
        np.save(emb_path, np.array([vec_cached]))
        with idx_path.open("w", encoding="utf-8") as f:
            json.dump({"items": [{"id": "mem_001", "row": 0}]}, f)

        encode_calls = []

        class FakeModel:
            def encode(self, texts, **kwargs):
                encode_calls.extend(texts)
                return np.ones((len(texts), 2), dtype=np.float32)

        monkeypatch.setattr(
            "src.memory.embedding_store._load_sentence_transformer",
            lambda model_name: FakeModel(),
        )

        rebuild_embedding_index(
            memory_path=mem_path,
            embeddings_path=emb_path,
            index_path=idx_path,
        )

        # Solo mem_002 debe haberse codificado (mem_001 ya estaba en caché)
        assert len(encode_calls) == 1
        assert encode_calls[0] == "Mbappé marcó hat-trick"

    def test_indice_resultante_tiene_ambas_memorias(self, tmp_path, monkeypatch):
        from src.memory.embedding_store import rebuild_embedding_index

        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"
        mem_path = self._make_memory_file(tmp_path, [
            {"id": "mem_001", "query_text": "texto 1", "fecha": "2026-01-01",
             "category": "c", "manager": "M", "player": None, "importance": 1, "summary": "s"},
            {"id": "mem_002", "query_text": "texto 2", "fecha": "2026-01-02",
             "category": "c", "manager": "M", "player": None, "importance": 1, "summary": "s"},
        ])

        class FakeModel:
            def encode(self, texts, **kwargs):
                return np.ones((len(texts), 4), dtype=np.float32)

        monkeypatch.setattr(
            "src.memory.embedding_store._load_sentence_transformer",
            lambda model_name: FakeModel(),
        )

        index = rebuild_embedding_index(
            memory_path=mem_path,
            embeddings_path=emb_path,
            index_path=idx_path,
        )

        assert index["count"] == 2
        ids_en_indice = [item["id"] for item in index["items"]]
        assert "mem_001" in ids_en_indice
        assert "mem_002" in ids_en_indice
