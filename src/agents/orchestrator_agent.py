"""
OrchestratorAgent - Coordina el WriterAgent (texto) y dispara en paralelo la
búsqueda de las fotos de portada.

Usa Groq (Llama 3.3 70B) como modelo barato para coordinar el texto.
Reserva Gemini para el WriterAgent, donde la calidad del texto importa.

Las dos fotos de portada (fichajes/jornada) ya no se piden como tool calls
que Groq deba secuenciar: se buscan con run_image_pipeline (sin LLM) en
paralelo con ThreadPoolExecutor antes de invocar al agente de texto, y se
cachean por jugador+equipo para no repetir la búsqueda en Bing si el mismo
jugador vuelve a salir en portada otro día (hallazgo IA-07).
"""

import json
import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from pathlib import Path

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

from src.agents.image_agent import run_image_pipeline
from src.agents.writer_agent import run_writer_agent
from src.utils.config_loader import load_config
from src.utils.llm_logger import log_llm_call

_GROQ_MODEL_NAME = "groq/llama-3.3-70b-versatile"

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


def _cache_key(jugador: str, equipo: str) -> str:
    raw = f"{jugador}_{equipo}".lower().strip()
    return "".join(c if c.isalnum() else "_" for c in raw).strip("_") or "sin_nombre"


def _fetch_portada_image(jugador: str, equipo: str, save_path: str, cache_dir: Path) -> bool:
    """
    Busca y guarda la foto de portada de un jugador, reutilizando una copia
    en cache si ya se descargó antes para el mismo jugador+equipo (hallazgo
    IA-07): evita repetir la búsqueda en Bing y el scoring con CLIP cuando
    el mismo MVP/fichaje vuelve a salir en portada otro día.

    Usa run_image_pipeline (sin LLM) en vez de run_image_agent: es la misma
    cadena search -> evaluate -> download, pero invocada directamente en
    Python, lo que permite llamarla en paralelo para las dos portadas sin
    depender de que Groq orqueste correctamente dos tool calls a Gemini.
    """
    cache_path = cache_dir / f"{_cache_key(jugador, equipo)}.jpg"
    if cache_path.exists():
        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            shutil.copyfile(cache_path, save_path)
            logger.info("[Orchestrator] Portada de %s recuperada de cache (%s)", jugador, cache_path.name)
            return True
        except Exception as e:
            logger.warning("[Orchestrator] No se pudo copiar desde cache (%s), se vuelve a descargar: %s", cache_path, e)

    success = run_image_pipeline(jugador, equipo, save_path)
    if success and os.path.exists(save_path):
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(save_path, cache_path)
        except Exception as e:
            logger.debug("[Orchestrator] No se pudo guardar en cache %s: %s", cache_path, e)
    return success


def run_orchestrator(
    prompt: str,
    portada_fichajes: dict,
    portada_jornada: dict,
    path_fichajes: str,
    path_jornada: str,
) -> dict | None:
    """Usa el OrchestratorAgent (Groq) para el texto; las dos fotos de
    portada se buscan en paralelo con Python plano (ver _fetch_portada_image),
    no como tool calls que Groq deba secuenciar (hallazgo IA-07)."""
    jugador_fichajes = portada_fichajes.get("jugador", "")
    equipo_fichajes = portada_fichajes.get("equipo", "")
    jugador_jornada = portada_jornada.get("jugador", "")
    equipo_jornada = portada_jornada.get("equipo", "")

    logger.info("[Orchestrator] Iniciando pipeline con Groq...")
    logger.info("[Orchestrator] Prompt: %s chars", len(prompt))

    cache_dir = Path(path_fichajes).resolve().parent / "cache"
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_fichajes = executor.submit(_fetch_portada_image, jugador_fichajes, equipo_fichajes, path_fichajes, cache_dir)
        future_jornada = executor.submit(_fetch_portada_image, jugador_jornada, equipo_jornada, path_jornada, cache_dir)
        ok_fichajes = future_fichajes.result()
        ok_jornada = future_jornada.result()
    logger.info(
        "[Orchestrator] Portadas listas (paralelo) — fichajes=%s jornada=%s",
        "OK" if ok_fichajes else "FALLBACK", "OK" if ok_jornada else "FALLBACK",
    )

    run_writer_tool, writer_cache = _make_run_writer_tool(prompt)
    agent = Agent(
        model=create_groq_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[run_writer_tool],
    )

    start = time.perf_counter()
    agent_error = None
    try:
        response = agent(
            f"""Genera el texto del periodico de la Sotano League ejecutando esta tool:

1. run_writer con prompt_ref="current_prompt"

IMPORTANTE:
- El prompt completo ya esta capturado internamente en run_writer.
- Para generar el texto, llama a run_writer usando exactamente prompt_ref="current_prompt".
- El prompt completo tiene {len(prompt)} caracteres; no lo copies en tus argumentos."""
        )
    except Exception as e:
        response = None
        agent_error = str(e)
    latency_ms = int((time.perf_counter() - start) * 1000)

    response_str = str(response) if response is not None else ""

    # El cache del tool run_writer es la fuente más fiable: se rellena
    # directamente cuando el WriterAgent tiene éxito, sin depender de que
    # Groq reproduzca el JSON literalmente en su respuesta final de texto.
    if writer_cache.get("cards"):
        logger.info("[Orchestrator] Cards recuperadas del cache del tool (sin segundo llamado a Gemini)")
        log_llm_call(
            component="orchestrator_agent.run_orchestrator", provider="groq", model=_GROQ_MODEL_NAME,
            success=True, latency_ms=latency_ms, metadata={"source": "tool_cache"},
        )
        return writer_cache["cards"]

    # Fallback: Groq a veces incluye el JSON de las tools en su respuesta
    # de texto aunque el cache no se haya rellenado; lo intentamos extraer.
    cards_payload = _extract_cards_payload(response_str)
    if cards_payload:
        logger.info("[Orchestrator] Pipeline completo - %s cards (extraídas de la respuesta)", len(cards_payload["cards"]))
        log_llm_call(
            component="orchestrator_agent.run_orchestrator", provider="groq", model=_GROQ_MODEL_NAME,
            success=True, latency_ms=latency_ms, metadata={"source": "response_extraction"},
        )
        return cards_payload

    # Último recurso: run_writer nunca llegó a ejecutarse, reintentamos directo.
    # Las portadas ya se buscaron en paralelo al principio de la función
    # independientemente de este fallback, así que aquí solo hace falta
    # reintentar el texto.
    logger.warning("[Orchestrator] No se pudieron extraer las cards, intentando fallback directo...")
    log_llm_call(
        component="orchestrator_agent.run_orchestrator", provider="groq", model=_GROQ_MODEL_NAME,
        success=False, latency_ms=latency_ms, error=agent_error or "no cards extraídas de la respuesta de Groq",
    )
    cards = run_writer_agent(prompt)
    if cards:
        return cards

    return None


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

Coordinas al WriterAgent, que genera el contenido textual (cards del periodico).
Las fotos de portada se buscan aparte, en paralelo, antes de llamarte a ti.

Cuando se te pida generar el texto del periodico:
1. Llama a run_writer con prompt_ref="current_prompt"

Reporta el resultado al finalizar.
""".strip()


