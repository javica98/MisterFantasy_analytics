"""
Tests unitarios para src/memory/memory_store.py
Cubre: delete_memories (usado por scripts/manage_memories.py)
"""
from src.memory.memory_store import delete_memories, read_memories, upsert_memories


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
