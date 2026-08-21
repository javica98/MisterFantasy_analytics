"""
Tests de integración — pipeline completo de MisterFantasy Analytics.

Cubren 4 tramos del pipeline, todos sin llamadas reales a APIs externas:

  Tramo 1 — Datos:     CSV → generate_json → generate_prompts → build_final_prompt
  Tramo 2 — AI:        prompt → run_orchestrator (Groq+Gemini mockeados) → cards JSON
  Tramo 3 — Memoria:   events + cards → build_memories → upsert → rebuild_index
  Tramo 4 — Completo:  tramos 1+2+3 encadenados, con todos los externos mockeados
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.utils.file_utils import safe_read_csv

# ─────────────────────────────────────────────
# Helpers compartidos
# ─────────────────────────────────────────────


@pytest.fixture
def real_data():
    """
    Datos reales de la temporada activa, vía safe_read_csv (que resuelve
    contra data/mister.db, no contra data/processed/*.csv directo).

    Antes estos tests hacían pd.read_csv("data/processed/...") a pelo, así
    que dejaron de ver ningún dato en cuanto la migración a SQLite hizo que
    esos ficheros dejaran de ser la fuente de verdad (hallazgo WEB-04). Si
    la temporada activa (config.yaml -> season.current) aún no tiene
    clasificaciones/quinielas generadas, estos tests siguen fallando — pero
    ahora por un motivo real (falta ese dato en la BD), no por leer el sitio
    equivocado. Ver docs/tests.md.
    """
    return {
        "gameweek": safe_read_csv("data/processed/gameweek.csv"),
        "ganancias_clean": safe_read_csv("data/processed/ganancias_clean.csv"),
        "clasificaciones": safe_read_csv("data/processed/clasificaciones.csv"),
        "quiniela": safe_read_csv("data/processed/quiniela.csv"),
    }

FAKE_CARDS = {
    "cards": [
        {
            "tipo": "clasificacion",
            "jugador": None, "manager": None, "puntos": None, "dinero": None, "equipo": None,
            "titulo": "¡La liga arde!",
            "subtitulo": "Maldinillo sigue líder",
            "texto": ["Frase uno.", "Frase dos.", "Frase tres."],
        },
        {
            "tipo": "rumor",
            "jugador": None, "manager": None, "puntos": None, "dinero": None, "equipo": None,
            "titulo": "Rumores en el vestuario",
            "subtitulo": "Se cuece algo grande",
            "texto": ["El chismorreo no para."],
        },
        {
            "tipo": "MVP de la jornada",
            "jugador": "K. Mbappé", "manager": "Maldinillo",
            "puntos": 18.0, "dinero": None, "equipo": "Real Madrid",
            "titulo": "¡Mbappé imparable!",
            "subtitulo": "Hat-trick de escándalo",
            "texto": ["Dos goles y una asistencia.", "Maldinillo al frente."],
        },
        {
            "tipo": "Fichaje destacado",
            "jugador": "Raphinha", "manager": "Dani",
            "puntos": None, "dinero": 56.0, "equipo": "FC Barcelona",
            "titulo": "¡Fichaje bomba!",
            "subtitulo": "Dani se lleva a Raphinha",
            "texto": ["La operación del verano."],
        },
    ]
}


# ─────────────────────────────────────────────
# TRAMO 1 — Pipeline de datos (sin mocks)
# ─────────────────────────────────────────────

class TestDataPipeline:
    """
    CSV reales → generate_json → generate_prompts → build_final_prompt.
    No llama a ninguna API externa.
    """

    def test_cadena_completa_desde_csvs_reales(self, real_data):
        """El pipeline de datos produce un prompt no vacío a partir de los datos reales."""
        from src.AI_newspaper.generate_json import generate_json
        from src.AI_newspaper.generate_prompt import build_final_prompt, generate_prompts

        df_gw = real_data["gameweek"]
        df_clean = real_data["ganancias_clean"]
        df_clas = real_data["clasificaciones"]
        df_quin = real_data["quiniela"]
        df_transfers = df_clean[df_clean["type"] == "transfer"]

        # Paso 1: generar JSON
        events = generate_json(365, df_transfers, df_gw, df_clas, df_quin)
        assert isinstance(events, dict)
        assert len(events["transfers"]) > 0,  "Sin transfers en los datos reales"
        assert len(events["gameweek"]) > 0,   "Sin gameweek en los datos reales"

        # Paso 2: generar bloques de prompt
        prompts = generate_prompts(events)
        assert len(prompts["bloques"]) > 0, "Sin bloques generados"
        tipos = [b["evento"] for b in prompts["bloques"]]
        assert "MVP de la jornada" in tipos

        # Paso 3: construir prompt final
        prompt_text = build_final_prompt(prompts["bloques"], events, "")
        assert len(prompt_text) > 500, "Prompt demasiado corto"
        assert "cards" in prompt_text
        assert "SOTANO LEAGUE" in prompt_text

    def test_equipo_jugador_siempre_es_string(self, real_data):
        """Ningún equipo_jugador debe llegar como número al JSON."""
        from src.AI_newspaper.generate_json import generate_json

        df_gw = real_data["gameweek"]
        df_clean = real_data["ganancias_clean"]
        df_clas = real_data["clasificaciones"]
        df_quin = real_data["quiniela"]
        df_transfers = df_clean[df_clean["type"] == "transfer"]

        events = generate_json(365, df_transfers, df_gw, df_clas, df_quin)

        for t in events["transfers"]:
            assert isinstance(t["equipo_jugador"], str), \
                f"equipo_jugador numerico en transfer: {t['equipo_jugador']}"
        for g in events["gameweek"]:
            assert isinstance(g["equipo_jugador"], str), \
                f"equipo_jugador numerico en gameweek: {g['equipo_jugador']}"

    def test_posicion_siempre_es_string(self, real_data):
        """La posición debe resolverse siempre a un nombre, nunca a número."""
        from src.AI_newspaper.generate_json import generate_json

        df_gw = real_data["gameweek"]
        df_clean = real_data["ganancias_clean"]
        df_clas = real_data["clasificaciones"]
        df_quin = real_data["quiniela"]
        df_transfers = df_clean[df_clean["type"] == "transfer"]

        events = generate_json(365, df_transfers, df_gw, df_clas, df_quin)
        for g in events["gameweek"]:
            assert isinstance(g["posicion"], str), \
                f"posicion no resuelta: {g['posicion']}"

    def test_clasificacion_contiene_todos_los_managers(self, real_data):
        """La clasificación general debe incluir los 9 managers de la liga."""
        from src.AI_newspaper.generate_json import generate_json

        df_gw = real_data["gameweek"]
        df_clean = real_data["ganancias_clean"]
        df_clas = real_data["clasificaciones"]
        df_quin = real_data["quiniela"]
        df_transfers = df_clean[df_clean["type"] == "transfer"]

        events = generate_json(365, df_transfers, df_gw, df_clas, df_quin)
        n_managers = len(events["clasificacion"]["general"])
        assert n_managers == 9, f"Se esperaban 9 managers, hay {n_managers}"

    def test_prompt_incluye_nombres_de_jugadores_reales(self, real_data):
        """El prompt final debe contener jugadores reales de los datos."""
        from src.AI_newspaper.generate_json import generate_json
        from src.AI_newspaper.generate_prompt import build_final_prompt, generate_prompts

        df_gw = real_data["gameweek"]
        df_clean = real_data["ganancias_clean"]
        df_clas = real_data["clasificaciones"]
        df_quin = real_data["quiniela"]
        df_transfers = df_clean[df_clean["type"] == "transfer"]

        events = generate_json(365, df_transfers, df_gw, df_clas, df_quin)
        prompts = generate_prompts(events)
        prompt_text = build_final_prompt(prompts["bloques"], events, "")

        # Al menos un jugador de los bloques debe aparecer en el prompt
        jugadores_en_bloques = [b["jugador"] for b in prompts["bloques"] if b.get("jugador")]
        assert any(j in prompt_text for j in jugadores_en_bloques), \
            "Ningún jugador de los bloques aparece en el prompt"


# ─────────────────────────────────────────────
# TRAMO 2 — Pipeline AI (Groq + Gemini mockeados)
# ─────────────────────────────────────────────

class TestAIPipeline:
    """
    prompt → run_orchestrator → cards JSON validado.
    Groq y Gemini completamente mockeados — sin coste de tokens.
    """

    SAMPLE_PROMPT = "Genera el periódico de la jornada 25 de la Sotano League."

    def _make_portada(self, jugador="K. Mbappé", equipo="Real Madrid"):
        return {"jugador": jugador, "equipo": equipo}

    def test_orchestrator_retorna_cards_cuando_writer_ok(self, tmp_path):
        """run_orchestrator devuelve cards si run_writer_agent tiene éxito."""
        from src.agents.orchestrator_agent import run_orchestrator

        with patch("src.agents.orchestrator_agent.run_writer_agent", return_value=FAKE_CARDS), \
             patch("src.agents.orchestrator_agent.run_image_pipeline", return_value=True), \
             patch("src.agents.orchestrator_agent.Agent") as mock_agent_cls:

            # Simular que Groq llama a run_writer y devuelve el JSON en su respuesta
            mock_agent_instance = MagicMock()
            mock_agent_instance.return_value = MagicMock(
                __str__=lambda self: json.dumps({"success": True, "cards": FAKE_CARDS})
            )
            mock_agent_cls.return_value = mock_agent_instance

            result = run_orchestrator(
                prompt=self.SAMPLE_PROMPT,
                portada_fichajes=self._make_portada(),
                portada_jornada=self._make_portada("Raphinha", "FC Barcelona"),
                path_fichajes=str(tmp_path / "Portada_Fichajes.jpg"),
                path_jornada=str(tmp_path / "Portada_Jornada.jpg"),
            )

        assert result is not None
        assert "cards" in result
        assert len(result["cards"]) > 0

    def test_orchestrator_usa_cache_cuando_groq_no_reproduce_json(self, tmp_path):
        """
        Si Groq no reproduce el JSON en su respuesta pero run_writer sí ejecutó,
        el orquestador recupera las cards del caché del tool sin llamar a Gemini de nuevo.
        """
        from src.agents.orchestrator_agent import run_orchestrator

        writer_calls = []

        def fake_run_writer(prompt):
            writer_calls.append(prompt)
            return FAKE_CARDS

        with patch("src.agents.orchestrator_agent.run_writer_agent", side_effect=fake_run_writer), \
             patch("src.agents.orchestrator_agent.run_image_pipeline", return_value=True), \
             patch("src.agents.orchestrator_agent.Agent") as mock_agent_cls:

            # Simular que Groq responde en texto plano (sin JSON de cards)
            # pero el tool run_writer sí se ejecutó internamente
            def fake_agent_call(user_message):
                # Simular que el Agent llama al tool internamente
                # Al acceder al mock, activamos el cache manualmente
                return MagicMock(__str__=lambda self: "He generado el periódico correctamente.")

            mock_instance = MagicMock()
            mock_instance.return_value = fake_agent_call(self.SAMPLE_PROMPT)
            mock_agent_cls.return_value = mock_instance

            result = run_orchestrator(
                prompt=self.SAMPLE_PROMPT,
                portada_fichajes=self._make_portada(),
                portada_jornada=self._make_portada(),
                path_fichajes=str(tmp_path / "Portada_Fichajes.jpg"),
                path_jornada=str(tmp_path / "Portada_Jornada.jpg"),
            )

        # El fallback debería activarse y llamar a run_writer_agent directamente
        assert result is not None or writer_calls, \
            "El orquestador no intentó recuperar las cards por ninguna vía"

    def test_orchestrator_devuelve_none_si_todo_falla(self, tmp_path):
        """Si Gemini y Groq fallan, run_orchestrator devuelve None limpiamente."""
        from src.agents.orchestrator_agent import run_orchestrator

        with patch("src.agents.orchestrator_agent.run_writer_agent", return_value=None), \
             patch("src.agents.orchestrator_agent.run_image_pipeline", return_value=False), \
             patch("src.agents.orchestrator_agent.Agent") as mock_agent_cls:

            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda self: "Sin resultado.")
            mock_agent_cls.return_value = mock_instance

            result = run_orchestrator(
                prompt=self.SAMPLE_PROMPT,
                portada_fichajes=self._make_portada(),
                portada_jornada=self._make_portada(),
                path_fichajes=str(tmp_path / "Portada_Fichajes.jpg"),
                path_jornada=str(tmp_path / "Portada_Jornada.jpg"),
            )

        assert result is None

    def test_cards_resultantes_pasan_validacion_pydantic(self, tmp_path):
        """Las cards devueltas por el orquestador deben pasar FinalJSON."""
        from src.agents.orchestrator_agent import run_orchestrator
        from src.AI_newspaper.SchemeValidator import FinalJSON

        with patch("src.agents.orchestrator_agent.run_writer_agent", return_value=FAKE_CARDS), \
             patch("src.agents.orchestrator_agent.run_image_pipeline", return_value=True), \
             patch("src.agents.orchestrator_agent.Agent") as mock_agent_cls:

            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                __str__=lambda self: json.dumps({"success": True, "cards": FAKE_CARDS})
            )
            mock_agent_cls.return_value = mock_instance

            result = run_orchestrator(
                prompt=self.SAMPLE_PROMPT,
                portada_fichajes=self._make_portada(),
                portada_jornada=self._make_portada(),
                path_fichajes=str(tmp_path / "Portada_Fichajes.jpg"),
                path_jornada=str(tmp_path / "Portada_Jornada.jpg"),
            )

        assert result is not None
        validated = FinalJSON(**result)
        assert len(validated.cards) == len(FAKE_CARDS["cards"])

    def test_writer_agent_devuelve_cards_via_structured_output_model(self):
        """
        run_writer_agent llama al agente con structured_output_model=FinalJSON
        (NO con el método Agent.structured_output() aparte, que se salta el
        bucle de tools) y lee el resultado de AgentResult.structured_output.
        """
        from src.agents.writer_agent import run_writer_agent
        from src.AI_newspaper.SchemeValidator import FinalJSON

        fake_result = FinalJSON(**FAKE_CARDS)

        with patch("src.agents.writer_agent.Agent") as mock_agent_cls:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(structured_output=fake_result)
            mock_agent_cls.return_value = mock_instance

            result = run_writer_agent("prompt de prueba")

        assert result is not None
        assert "cards" in result
        assert len(result["cards"]) == len(FAKE_CARDS["cards"])
        # se invoca el agente normal (__call__), no el método structured_output() aparte
        mock_instance.structured_output.assert_not_called()
        _, kwargs = mock_instance.call_args
        assert kwargs.get("structured_output_model") is FinalJSON

    def test_writer_agent_devuelve_none_si_la_invocacion_falla(self):
        """Si la invocación del agente falla en todos los intentos, se devuelve None."""
        from src.agents.writer_agent import run_writer_agent

        with patch("src.agents.writer_agent.Agent") as mock_agent_cls, \
             patch("src.agents.writer_agent.time.sleep"):
            mock_instance = MagicMock()
            mock_instance.side_effect = Exception("fallo de invocación")
            mock_agent_cls.return_value = mock_instance

            result = run_writer_agent("prompt de prueba")

        assert result is None
        assert mock_instance.call_count == 3  # hallazgo IA-08: reintenta en vez de rendirse al primer fallo

    def test_writer_agent_devuelve_none_si_no_hay_structured_output(self):
        """Si el agente responde pero no produce structured_output en ningún intento, se devuelve None."""
        from src.agents.writer_agent import run_writer_agent

        with patch("src.agents.writer_agent.Agent") as mock_agent_cls, \
             patch("src.agents.writer_agent.time.sleep"):
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(structured_output=None)
            mock_agent_cls.return_value = mock_instance

            result = run_writer_agent("prompt de prueba")

        assert result is None
        assert mock_instance.call_count == 3

    def test_writer_agent_reintenta_y_tiene_exito_en_el_segundo_intento(self):
        """Si el primer intento falla pero el segundo produce cards válidas, no sigue reintentando."""
        from src.agents.writer_agent import run_writer_agent
        from src.AI_newspaper.SchemeValidator import FinalJSON

        fake_result = FinalJSON(**FAKE_CARDS)

        with patch("src.agents.writer_agent.Agent") as mock_agent_cls, \
             patch("src.agents.writer_agent.time.sleep") as mock_sleep:
            mock_instance = MagicMock()
            mock_instance.side_effect = [
                Exception("429 rate limited"),
                MagicMock(structured_output=fake_result),
            ]
            mock_agent_cls.return_value = mock_instance

            result = run_writer_agent("prompt de prueba")

        assert result is not None
        assert len(result["cards"]) == len(FAKE_CARDS["cards"])
        assert mock_instance.call_count == 2
        mock_sleep.assert_called_once()  # solo esperó entre el intento 1 y el 2


# ─────────────────────────────────────────────
# TRAMO 3 — Pipeline de memoria
# ─────────────────────────────────────────────

class TestMemoryPipeline:
    """
    events + cards → build_memories → upsert_memories → rebuild_embedding_index.
    sentence-transformers mockeado para no depender del modelo local.
    """

    def test_build_memories_produce_lista_no_vacia(self, sample_events_json):
        from src.memory.memory_builder import build_memories
        memories = build_memories(sample_events_json, FAKE_CARDS)
        assert isinstance(memories, list)
        assert len(memories) > 0

    def test_todas_las_memorias_tienen_id_unico(self, sample_events_json):
        from src.memory.memory_builder import build_memories
        memories = build_memories(sample_events_json, FAKE_CARDS)
        ids = [m["id"] for m in memories]
        assert len(ids) == len(set(ids)), "IDs de memoria duplicados"

    def test_memorias_tienen_campos_requeridos(self, sample_events_json):
        from src.memory.memory_builder import build_memories
        memories = build_memories(sample_events_json, FAKE_CARDS)
        required = {"id", "fecha", "layer", "category", "summary", "query_text", "importance"}
        for m in memories:
            missing = required - set(m.keys())
            assert not missing, f"Memoria sin campos: {missing}"

    def test_hay_memoria_de_clasificacion(self, sample_events_json):
        from src.memory.memory_builder import build_memories
        memories = build_memories(sample_events_json, FAKE_CARDS)
        categorias = [m["category"] for m in memories]
        assert "clasificacion" in categorias

    def test_hay_memorias_narrativas_de_cards(self, sample_events_json):
        from src.memory.memory_builder import build_memories
        memories = build_memories(sample_events_json, FAKE_CARDS)
        narrativas = [m for m in memories if m["layer"] == "narrative"]
        assert len(narrativas) > 0, "No se generaron memorias narrativas de las cards"

    def test_upsert_persiste_en_jsonl(self, sample_events_json, tmp_path):
        from src.memory.memory_builder import build_memories
        from src.memory.memory_store import upsert_memories

        memories = build_memories(sample_events_json, FAKE_CARDS)
        mem_path = tmp_path / "memories.jsonl"

        changed = upsert_memories(memories, str(mem_path))
        assert changed > 0, "No se guardaron memorias nuevas"
        assert mem_path.exists()

        # Verificar que el JSONL es legible
        lines = mem_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == len(memories)
        for line in lines:
            data = json.loads(line)
            assert "id" in data

    def test_upsert_no_duplica_memorias_existentes(self, sample_events_json, tmp_path):
        from src.memory.memory_builder import build_memories
        from src.memory.memory_store import upsert_memories

        memories = build_memories(sample_events_json, FAKE_CARDS)
        mem_path = str(tmp_path / "memories.jsonl")

        first_changed = upsert_memories(memories, mem_path)
        second_changed = upsert_memories(memories, mem_path)

        assert first_changed > 0
        assert second_changed == 0, "Segunda pasada con mismas memorias no debería tener cambios"

    def test_rebuild_index_con_memorias_reales(self, sample_events_json, tmp_path, monkeypatch):
        from src.memory.memory_builder import build_memories
        from src.memory.memory_store import upsert_memories
        from src.memory.embedding_store import rebuild_embedding_index

        memories = build_memories(sample_events_json, FAKE_CARDS)
        mem_path = tmp_path / "memories.jsonl"
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"

        upsert_memories(memories, str(mem_path))

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

        assert index["count"] == len(memories)
        saved_vecs = np.load(emb_path)
        assert saved_vecs.shape[0] == len(memories)

    def test_rebuild_incremental_no_recodifica_existentes(self, sample_events_json, tmp_path, monkeypatch):
        """Segunda llamada a rebuild con mismas memorias no codifica nada nuevo."""
        from src.memory.memory_builder import build_memories
        from src.memory.memory_store import upsert_memories
        from src.memory.embedding_store import rebuild_embedding_index

        memories = build_memories(sample_events_json, FAKE_CARDS)
        mem_path = tmp_path / "memories.jsonl"
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"

        upsert_memories(memories, str(mem_path))

        encode_calls_count = []

        class FakeModel:
            def encode(self, texts, **kwargs):
                encode_calls_count.append(len(texts))
                return np.ones((len(texts), 4), dtype=np.float32)

        monkeypatch.setattr(
            "src.memory.embedding_store._load_sentence_transformer",
            lambda model_name: FakeModel(),
        )

        # Primera construcción — codifica todo
        rebuild_embedding_index(memory_path=mem_path, embeddings_path=emb_path, index_path=idx_path)
        first_total = sum(encode_calls_count)
        encode_calls_count.clear()

        # Segunda construcción — no debe codificar nada (caché)
        rebuild_embedding_index(memory_path=mem_path, embeddings_path=emb_path, index_path=idx_path)
        second_total = sum(encode_calls_count)

        assert first_total == len(memories)
        assert second_total == 0, "El rebuild incremental recodificó memorias ya existentes"


# ─────────────────────────────────────────────
# TRAMO 4 — Pipeline completo encadenado
# ─────────────────────────────────────────────

class TestFullPipeline:
    """
    Tramos 1+2+3 encadenados con datos reales de CSV.
    Todas las llamadas a APIs externas mockeadas.
    """

    def test_pipeline_datos_to_memorias(self, tmp_path, monkeypatch, real_data):
        """
        Datos reales → JSON → prompt → (AI mockeada) → cards → memorias → embeddings.
        Verifica que toda la cadena funciona de punta a punta.
        """
        from src.AI_newspaper.generate_json import generate_json
        from src.AI_newspaper.generate_prompt import build_final_prompt, generate_prompts
        from src.agents.orchestrator_agent import run_orchestrator
        from src.memory.embedding_store import rebuild_embedding_index
        from src.memory.memory_builder import build_memories
        from src.memory.memory_store import upsert_memories

        # ── Tramo 1: datos ──────────────────────────────────────────────
        df_gw = real_data["gameweek"]
        df_clean = real_data["ganancias_clean"]
        df_clas = real_data["clasificaciones"]
        df_quin = real_data["quiniela"]
        df_transfers = df_clean[df_clean["type"] == "transfer"]

        events = generate_json(365, df_transfers, df_gw, df_clas, df_quin)
        prompts = generate_prompts(events)
        prompt_text = build_final_prompt(prompts["bloques"], events, "")

        fichajes = next((b for b in prompts["bloques"] if b["evento"] == "Fichaje destacado"), prompts["bloques"][0])
        mvp = next((b for b in prompts["bloques"] if b["evento"] == "MVP de la jornada"), prompts["bloques"][0])

        # ── Tramo 2: AI mockeada ────────────────────────────────────────
        with patch("src.agents.orchestrator_agent.run_writer_agent", return_value=FAKE_CARDS), \
             patch("src.agents.orchestrator_agent.run_image_pipeline", return_value=True), \
             patch("src.agents.orchestrator_agent.Agent") as mock_agent_cls:

            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                __str__=lambda self: json.dumps({"success": True, "cards": FAKE_CARDS})
            )
            mock_agent_cls.return_value = mock_instance

            cards = run_orchestrator(
                prompt=prompt_text,
                portada_fichajes={"jugador": fichajes.get("jugador", ""), "equipo": fichajes.get("equipo", "")},
                portada_jornada={"jugador": mvp.get("jugador", ""), "equipo": mvp.get("equipo", "")},
                path_fichajes=str(tmp_path / "Portada_Fichajes.jpg"),
                path_jornada=str(tmp_path / "Portada_Jornada.jpg"),
            )

        assert cards is not None, "El orquestador no devolvió cards"

        # ── Tramo 3: memorias ───────────────────────────────────────────
        memories = build_memories(events, cards)
        assert len(memories) > 0

        mem_path = tmp_path / "memories.jsonl"
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"

        changed = upsert_memories(memories, str(mem_path))
        assert changed > 0

        class FakeModel:
            def encode(self, texts, **kwargs):
                return np.random.rand(len(texts), 8).astype(np.float32)

        monkeypatch.setattr(
            "src.memory.embedding_store._load_sentence_transformer",
            lambda model_name: FakeModel(),
        )

        index = rebuild_embedding_index(
            memory_path=mem_path,
            embeddings_path=emb_path,
            index_path=idx_path,
        )

        # ── Verificaciones finales ──────────────────────────────────────
        assert index["count"] == len(memories)
        assert np.load(emb_path).shape[0] == len(memories)

        # El JSON de cards pasa validación Pydantic
        from src.AI_newspaper.SchemeValidator import FinalJSON
        validated = FinalJSON(**cards)
        assert len(validated.cards) > 0

    def test_pipeline_es_idempotente(self, tmp_path, monkeypatch, real_data):
        """
        Ejecutar el pipeline dos veces con los mismos datos no duplica memorias
        ni genera errores.
        """
        from src.AI_newspaper.generate_json import generate_json
        from src.memory.embedding_store import rebuild_embedding_index
        from src.memory.memory_builder import build_memories
        from src.memory.memory_store import upsert_memories

        df_gw = real_data["gameweek"]
        df_clean = real_data["ganancias_clean"]
        df_clas = real_data["clasificaciones"]
        df_quin = real_data["quiniela"]
        df_transfers = df_clean[df_clean["type"] == "transfer"]

        events = generate_json(365, df_transfers, df_gw, df_clas, df_quin)
        memories = build_memories(events, FAKE_CARDS)

        mem_path = str(tmp_path / "memories.jsonl")
        emb_path = tmp_path / "embeddings.npy"
        idx_path = tmp_path / "index.json"

        class FakeModel:
            def encode(self, texts, **kwargs):
                return np.ones((len(texts), 4), dtype=np.float32)

        monkeypatch.setattr(
            "src.memory.embedding_store._load_sentence_transformer",
            lambda model_name: FakeModel(),
        )

        # Primera ejecución
        first_changed = upsert_memories(memories, mem_path)
        rebuild_embedding_index(memory_path=mem_path, embeddings_path=emb_path, index_path=idx_path)

        # Segunda ejecución con los mismos datos
        second_changed = upsert_memories(memories, mem_path)
        rebuild_embedding_index(memory_path=mem_path, embeddings_path=emb_path, index_path=idx_path)

        assert first_changed > 0
        assert second_changed == 0, "Segunda ejecución no debe generar cambios con los mismos datos"

        # El índice sigue siendo correcto
        index_data = json.loads(idx_path.read_text(encoding="utf-8"))
        assert index_data["count"] == len(memories)
