"""
Tests unitarios para scripts/manage_memories.py (CLI de mantenimiento de memories.jsonl)
"""
import argparse

import pytest

from scripts.manage_memories import build_parser, cmd_delete, cmd_list, cmd_show
from src.memory.memory_store import read_memories, upsert_memories


def _memory(id_, **kwargs):
    base = {
        "id": id_,
        "fecha": "2026-03-01",
        "layer": "narrative",
        "category": "clasificacion",
        "manager": None,
        "player": None,
        "summary": f"resumen {id_}",
        "query_text": f"query {id_}",
        "importance": 1,
    }
    base.update(kwargs)
    return base


@pytest.fixture
def memories_path(tmp_path):
    path = tmp_path / "memories.jsonl"
    upsert_memories(
        [
            _memory("mvp_1", category="MVP de la jornada", manager="Maldinillo", player="Mbappé"),
            _memory("clasif_1", category="clasificacion"),
        ],
        path,
    )
    return path


class TestCmdList:
    def test_lista_todas_sin_filtros(self, memories_path, capsys):
        args = argparse.Namespace(
            path=str(memories_path), temporada=None, category=None, manager=None, player=None, query=None, limit=None
        )
        cmd_list(args)
        out = capsys.readouterr().out
        assert "mvp_1" in out
        assert "clasif_1" in out

    def test_filtra_por_category(self, memories_path, capsys):
        args = argparse.Namespace(
            path=str(memories_path), temporada=None, category="clasificacion", manager=None, player=None, query=None, limit=None
        )
        cmd_list(args)
        out = capsys.readouterr().out
        assert "clasif_1" in out
        assert "mvp_1" not in out

    def test_filtra_por_manager(self, memories_path, capsys):
        args = argparse.Namespace(
            path=str(memories_path), temporada=None, category=None, manager="Maldinillo", player=None, query=None, limit=None
        )
        cmd_list(args)
        out = capsys.readouterr().out
        assert "mvp_1" in out
        assert "clasif_1" not in out

    def test_filtra_por_temporada(self, tmp_path, capsys):
        path = tmp_path / "memories.jsonl"
        upsert_memories(
            [
                _memory("vieja", temporada="2025-26"),
                _memory("nueva", temporada="2026-27"),
            ],
            path,
        )
        args = argparse.Namespace(
            path=str(path), temporada="2026-27", category=None, manager=None, player=None, query=None, limit=None
        )
        cmd_list(args)
        out = capsys.readouterr().out
        assert "nueva" in out
        assert "vieja" not in out

    def test_sin_resultados_imprime_mensaje(self, memories_path, capsys):
        args = argparse.Namespace(
            path=str(memories_path), temporada=None, category="no_existe", manager=None, player=None, query=None, limit=None
        )
        cmd_list(args)
        out = capsys.readouterr().out
        assert "Sin resultados" in out


class TestCmdShow:
    def test_muestra_json_de_memoria_existente(self, memories_path, capsys):
        args = argparse.Namespace(path=str(memories_path), ids=["mvp_1"])
        cmd_show(args)
        out = capsys.readouterr().out
        assert '"id": "mvp_1"' in out
        assert '"manager": "Maldinillo"' in out

    def test_id_inexistente_avisa_sin_lanzar(self, memories_path, capsys):
        args = argparse.Namespace(path=str(memories_path), ids=["no_existe"])
        cmd_show(args)  # no debe lanzar
        out = capsys.readouterr().out
        assert "No existe" in out


class TestCmdDelete:
    def test_borra_con_yes_sin_pedir_confirmacion(self, memories_path, capsys):
        args = argparse.Namespace(path=str(memories_path), ids=["mvp_1"], yes=True, rebuild_index=False)
        cmd_delete(args)

        out = capsys.readouterr().out
        assert "Borrada(s) 1 memoria(s)" in out
        assert [m["id"] for m in read_memories(memories_path)] == ["clasif_1"]

    def test_cancela_si_usuario_no_confirma(self, memories_path, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        args = argparse.Namespace(path=str(memories_path), ids=["mvp_1"], yes=False, rebuild_index=False)
        cmd_delete(args)

        out = capsys.readouterr().out
        assert "Cancelado" in out
        assert "mvp_1" in [m["id"] for m in read_memories(memories_path)]

    def test_id_inexistente_no_borra_nada(self, memories_path, capsys):
        args = argparse.Namespace(path=str(memories_path), ids=["no_existe"], yes=True, rebuild_index=False)
        cmd_delete(args)

        out = capsys.readouterr().out
        assert "No existe una memoria" in out
        assert "Nada que borrar" in out
        assert len(read_memories(memories_path)) == 2


class TestBuildParser:
    def test_parsea_comando_list(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--category", "rumor"])
        assert args.command == "list"
        assert args.category == "rumor"

    def test_parsea_comando_delete_con_flags(self):
        parser = build_parser()
        args = parser.parse_args(["delete", "id1", "id2", "--yes", "--rebuild-index"])
        assert args.ids == ["id1", "id2"]
        assert args.yes is True
        assert args.rebuild_index is True
