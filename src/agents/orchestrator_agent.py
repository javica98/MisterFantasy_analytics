"""
OrchestratorAgent - Coordina WriterAgent e ImageAgent.

Usa Groq (Llama 3.3 70B) como modelo barato para coordinacion.
Reserva Gemini para el WriterAgent, donde la calidad del texto importa.
"""

import json
import logging
import os
from json import JSONDecodeError

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

from src.agents.image_agent import run_image_agent
from src.agents.writer_agent import run_writer_agent
from src.utils.config_loader import load_config

logger = logging.getLogger(__name__)

_cfg = load_config()
_GROQ_API_KEY = _cfg["env"].get("GROQ_API_KEY")

if not _GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY no encontrado en variables de entorno.")


def create_groq_model() -> LiteLLMModel:
    """Groq Llama 3.3 70B: suficiente para coordinacion de tools."""
    os.environ["GROQ_API_KEY"] = _GROQ_API_KEY
    return LiteLLMModel(
        model_id="groq/llama-3.3-70b-versatile",
        params={"temperature": 0.1, "max_tokens": 1024},
    )


def _make_run_writer_tool(prompt: str) -> tuple:
    """
    Devuelve (tool, cache) donde cache es un dict compartido.
    Cuando run_writer ejecuta con éxito, guarda las cards en cache['cards'].
    Esto permite que run_orchestrator recupere el resultado sin un segundo
    llamado a Gemini aunque Groq no reproduzca el JSON en su respuesta final.
    """
    cache: dict = {}

    def run_writer(prompt_ref: str) -> str:
        """
        Ejecuta el WriterAgent para generar las cards del periodico.

        Args:
            prompt_ref: Referencia al prompt completo. Usa exactamente "current_prompt".
        """
        if prompt_ref != "current_prompt":
            return json.dumps(
                {"success": False, "error": 'prompt_ref debe ser exactamente "current_prompt"'}
            )

        logger.info("[Orchestrator] -> WriterAgent")
        result = run_writer_agent(prompt)

        if result is None:
            return json.dumps({"success": False, "error": "WriterAgent no genero cards validas"})

        logger.info("[Orchestrator] <- WriterAgent OK (%s cards)", len(result.get("cards", [])))
        cache["cards"] = result  # guardar para recuperación sin segundo llamado
        return json.dumps({"success": True, "cards": result}, ensure_ascii=False)

    return tool(run_writer), cache


def run_orchestrator(
    prompt: str,
    portada_fichajes: dict,
    portada_jornada: dict,
    path_fichajes: str,
    path_jornada: str,
) -> dict | None:
    """Usa el OrchestratorAgent (Groq) para coordinar WriterAgent e ImageAgent."""
    jugador_fichajes = portada_fichajes.get("jugador", "")
    equipo_fichajes = portada_fichajes.get("equipo", "")
    jugador_jornada = portada_jornada.get("jugador", "")
    equipo_jornada = portada_jornada.get("equipo", "")

    logger.info("[Orchestrator] Iniciando pipeline con Groq...")
    logger.info("[Orchestrator] Prompt: %s chars", len(prompt))

    run_writer_tool, writer_cache = _make_run_writer_tool(prompt)
    agent = Agent(
        model=create_groq_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[run_writer_tool, run_image],
    )

    response = agent(
        f"""Genera el periodico completo de la Sotano League ejecutando estas 3 tools:

1. run_writer con prompt_ref="current_prompt"
2. run_image para portada Fichajes: jugador="{jugador_fichajes}", equipo="{equipo_fichajes}", save_path="{path_fichajes}"
3. run_image para portada Jornada: jugador="{jugador_jornada}", equipo="{equipo_jornada}", save_path="{path_jornada}"

IMPORTANTE:
- El prompt completo ya esta capturado internamente en run_writer.
- Para generar el texto, llama a run_writer usando exactamente prompt_ref="current_prompt".
- El prompt completo tiene {len(prompt)} caracteres; no lo copies en tus argumentos."""
    )

    response_str = str(response)
    cards_payload = _extract_cards_payload(response_str)
    if cards_payload:
        logger.info("[Orchestrator] Pipeline completo - %s cards", len(cards_payload["cards"]))
        return cards_payload

    # Groq a veces responde en texto plano sin reproducir el JSON de las tools.
    # Antes de llamar a Gemini de nuevo, comprobamos si run_writer ya guardó las cards.
    if writer_cache.get("cards"):
        logger.info("[Orchestrator] Cards recuperadas del cache del tool (sin segundo llamado a Gemini)")
        return writer_cache["cards"]

    # Fallback real: solo si run_writer nunca llegó a ejecutarse
    logger.warning("[Orchestrator] No se pudieron extraer las cards, intentando fallback directo...")
    cards = run_writer_agent(prompt)
    if cards:
        run_image_agent(jugador_fichajes, equipo_fichajes, path_fichajes)
        run_image_agent(jugador_jornada, equipo_jornada, path_jornada)
        return cards

    return None


@tool
def run_image(jugador: str, equipo: str, save_path: str) -> str:
    """
    Ejecuta el ImageAgent para buscar y descargar la mejor foto del jugador.

    Args:
        jugador: Nombre del jugador de portada.
        equipo: Equipo del jugador.
        save_path: Ruta donde guardar la imagen.
    """
    logger.info("[Orchestrator] -> ImageAgent (%s)", jugador)
    success = run_image_agent(jugador, equipo, save_path)
    logger.info("[Orchestrator] <- ImageAgent %s", "OK" if success else "FALLBACK")
    return json.dumps({"success": success, "path": save_path if success else None})


def _extract_cards_payload(response_str: str) -> dict | None:
    """Extrae {"cards": [...]} desde la respuesta final o salidas de tools."""
    decoder = json.JSONDecoder()

    for index, char in enumerate(response_str):
        if char != "{":
            continue

        try:
            parsed, _ = decoder.raw_decode(response_str[index:])
        except JSONDecodeError:
            continue

        cards_payload = _find_cards_payload(parsed)
        if cards_payload:
            return cards_payload

    return None


def _find_cards_payload(value) -> dict | None:
    if isinstance(value, dict):
        cards = value.get("cards")
        if isinstance(cards, list) and cards:
            return {"cards": cards}
        if isinstance(cards, dict):
            nested = _find_cards_payload(cards)
            if nested:
                return nested
        for child in value.values():
            nested = _find_cards_payload(child)
            if nested:
                return nested

    if isinstance(value, list):
        for child in value:
            nested = _find_cards_payload(child)
            if nested:
                return nested

    return None


ORCHESTRATOR_PROMPT = """
Eres el OrchestratorAgent del periodico fantasy SOTANO LEAGUE.

Coordinas dos agentes especializados:
- run_writer: genera el contenido textual (cards del periodico)
- run_image: busca y descarga la mejor foto de portada

Cuando se te pida generar el periodico completo:
1. Llama a run_writer con prompt_ref="current_prompt"
2. Llama a run_image para cada portada indicada

Reporta el resultado de todas las llamadas al finalizar.
""".strip()


