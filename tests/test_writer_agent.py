"""
Tests unitarios para src/agents/writer_agent.py
Cubre: retrieve_memory_context (tool de RAG bajo demanda) y la composición
de tools del WriterAgent.
"""
from unittest.mock import patch

from src.agents.writer_agent import create_writer_agent, retrieve_memory_context


class TestRetrieveMemoryContext:
    def test_devuelve_contexto_formateado_cuando_hay_memorias(self):
        fake_memories = [
            {
                "fecha": "2026-03-01",
                "category": "rumor",
                "manager": "Dani",
                "player": None,
                "summary": "Dani le robó un jugador a Maldinillo con un clausulazo.",
            },
        ]
        with patch("src.agents.writer_agent.retrieve_relevant_memories", return_value=fake_memories):
            result = retrieve_memory_context("rivalidad Dani Maldinillo")

        assert "Dani le robó un jugador a Maldinillo con un clausulazo." in result

    def test_mensaje_amigable_cuando_no_hay_memorias(self):
        with patch("src.agents.writer_agent.retrieve_relevant_memories", return_value=[]):
            result = retrieve_memory_context("consulta sin resultados")

        assert "Sin memorias relevantes" in result

    def test_respeta_top_k_pasado_a_retrieve_relevant_memories(self):
        with patch("src.agents.writer_agent.retrieve_relevant_memories", return_value=[]) as mock_retrieve:
            retrieve_memory_context("query", top_k=3)

        mock_retrieve.assert_called_once_with("query", top_k=3)

    def test_top_k_por_defecto_es_5(self):
        with patch("src.agents.writer_agent.retrieve_relevant_memories", return_value=[]) as mock_retrieve:
            retrieve_memory_context("query")

        mock_retrieve.assert_called_once_with("query", top_k=5)


class TestCreateWriterAgentTools:
    def test_incluye_las_tres_tools(self):
        agent = create_writer_agent()
        assert set(agent.tool_names) == {"generate_cards", "validate_cards", "retrieve_memory_context"}
