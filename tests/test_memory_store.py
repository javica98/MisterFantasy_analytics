"""
Tests unitarios para src/memory/memory_store.py
Cubre: delete_memories (usado por scripts/manage_memories.py) y el filtro
por temporada de retrieve_by_keywords (hallazgo IA-02).
"""
from src.memory.memory_store import delete_memories, read_memories, retrieve_by_keywords, upsert_memories


def _memory(id_, **kwargs):
    base = {
        "id": id_,
        "fecha": "2026-03-01",
        "layer": "narrative",
        "category": "clasificacion",
        "summary": f"resumen {id_}",
        "query_text": f"query {id_}",
        "importance": 1,
    }
    base.update(kwargs)
    return base


class TestDeleteMemories:
    def test_borra_memoria_existente(self, tmp_path):
        path = tmp_path / "memories.jsonl"
        upsert_memories([_memory("a"), _memory("b")], path)

        removed = delete_memories(["a"], path)

        assert removed == 1
        assert [m["id"] for m in read_memories(path)] == ["b"]

    def test_borrar_id_inexistente_no_afecta_nada(self, tmp_path):
        path = tmp_path / "memories.jsonl"
        upsert_memories([_memory("a")], path)

        removed = delete_memories(["no_existe"], path)

        assert removed == 0
        assert len(read_memories(path)) == 1

    def test_borra_varias_memorias_a_la_vez(self, tmp_path):
        path = tmp_path / "memories.jsonl"
        upsert_memories([_memory("a"), _memory("b"), _memory("c")], path)

        removed = delete_memories(["a", "c"], path)

        assert removed == 2
        assert [m["id"] for m in read_memories(path)] == ["b"]

    def test_archivo_inexistente_devuelve_cero(self, tmp_path):
        path = tmp_path / "no_existe.jsonl"
        assert delete_memories(["a"], path) == 0


class TestRetrieveByKeywordsTemporada:
    """
    Antes las memorias no tenían campo temporada y retrieve_by_keywords
    devolvía recuerdos de cualquier temporada mezclados sin distinción.
    Ahora, si se pasa `temporada`, solo deben salir los de esa temporada
    (hallazgo IA-02).
    """

    def test_sin_filtro_devuelve_de_cualquier_temporada(self, tmp_path):
        path = tmp_path / "memories.jsonl"
        upsert_memories(
            [
                _memory("a", temporada="2025-26", query_text="maldinillo clausulazo mbappe"),
                _memory("b", temporada="2026-27", query_text="maldinillo clausulazo mbappe"),
            ],
            path,
        )

        result = retrieve_by_keywords("maldinillo mbappe", path=path)

        assert {m["id"] for m in result} == {"a", "b"}

    def test_con_filtro_solo_devuelve_la_temporada_pedida(self, tmp_path):
        path = tmp_path / "memories.jsonl"
        upsert_memories(
            [
                _memory("a", temporada="2025-26", query_text="maldinillo clausulazo mbappe"),
                _memory("b", temporada="2026-27", query_text="maldinillo clausulazo mbappe"),
            ],
            path,
        )

        result = retrieve_by_keywords("maldinillo mbappe", path=path, temporada="2026-27")

        assert [m["id"] for m in result] == ["b"]

    def test_memorias_sin_temporada_no_salen_al_filtrar(self, tmp_path):
        path = tmp_path / "memories.jsonl"
        upsert_memories(
            [_memory("legacy", query_text="maldinillo clausulazo mbappe")],  # sin temporada
            path,
        )

        result = retrieve_by_keywords("maldinillo mbappe", path=path, temporada="2026-27")

        assert result == []
