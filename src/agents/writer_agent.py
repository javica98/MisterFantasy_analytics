"""
WriterAgent — Agente para generación de cards del periódico.

Responsabilidad única: recibir un prompt ya construido, llamar a Gemini
y validar el resultado. Reintenta automáticamente si el JSON no es válido.

Lo que NO hace este agente (se hace en código Python puro antes de llamarlo):
- Cargar CSVs
- Estructurar el JSON de eventos
- Construir el prompt

Flujo:
    1. generate_cards(prompt)  → llama a Gemini, devuelve cards
    2. validate_cards(cards)   → valida con Pydantic, reintenta si falla
"""

import json
import logging
from strands import Agent, tool
from strands.models.gemini import GeminiModel
from pydantic import ValidationError

from src.AI_newspaper.generate_article import generate_articles
from src.AI_newspaper.SchemeValidator import FinalJSON
from src.memory.memory_store import format_memory_context, retrieve_relevant_memories
from src.utils.config_loader import load_config

logger = logging.getLogger(__name__)

_cfg = load_config()
_GEMINI_API_KEY = _cfg["env"].get("GEMINI_API_KEY")

if not _GEMINI_API_KEY:
    raise ValueError("⚠️ GEMINI_API_KEY no encontrado en variables de entorno.")


def create_gemini_model(temperature: float = 0.5) -> GeminiModel:
    """Temperature media: el WriterAgent necesita creatividad pero no demasiada."""
    return GeminiModel(
        model_id="gemini-2.5-flash",
        client_args={"api_key": _GEMINI_API_KEY},
        params={"temperature": temperature},
    )


# ─────────────────────────────────────────────
# TOOL 1 — Llamada a Gemini
# ─────────────────────────────────────────────

@tool
def generate_cards(prompt: str) -> str:
    """
    Llama a Gemini con el prompt del periódico y devuelve las cards generadas.
    Llama a esta tool PRIMERO, pasando el prompt completo.

    Devuelve un JSON con las cards o un campo "error" si Gemini falla.

    Args:
        prompt: El texto del prompt completo para generar las cards del periódico.
    """
    logger.info(f"[Tool 1/2] generate_cards — llamando a Gemini ({len(prompt)} chars)")

    result = generate_articles(prompt, temperature=0.7)

    if not result:
        logger.error("[Tool 1/2] Gemini devolvió respuesta vacía")
        return json.dumps({"error": "Gemini devolvió respuesta vacía", "cards": None})

    if hasattr(result, "model_dump"):
        cards_dict = result.model_dump()
    elif isinstance(result, dict):
        cards_dict = result
    else:
        try:
            cards_dict = dict(result)
        except Exception:
            cards_dict = {"cards": []}

    num_cards = len(cards_dict.get("cards", []))
    logger.info(f"[Tool 1/2] OK — {num_cards} cards generadas")

    return json.dumps(cards_dict, ensure_ascii=False, default=str)


# ─────────────────────────────────────────────
# TOOL 2 — Validación con Pydantic
# ─────────────────────────────────────────────

@tool
def validate_cards(cards_json: str) -> str:
    """
    Valida que las cards generadas cumplen el schema del periódico.
    Llama a esta tool DESPUÉS de generate_cards.

    Si la validación falla, devuelve los errores para que puedas
    reintentar generate_cards con el mismo prompt.

    Args:
        cards_json: JSON string devuelto por generate_cards.
    """
    logger.info("[Tool 2/2] validate_cards — validando schema")

    try:
        data = json.loads(cards_json)
    except json.JSONDecodeError as e:
        return json.dumps({"valid": False, "errors": [f"JSON inválido: {e}"]})

    if "error" in data and data.get("cards") is None:
        return json.dumps({"valid": False, "errors": [data["error"]]})

    try:
        validated = FinalJSON(**data)
        tipos = [c.tipo for c in validated.cards]
        logger.info(f"[Tool 2/2] OK — {len(validated.cards)} cards válidas: {tipos}")

        return json.dumps({
            "valid": True,
            "errors": [],
            "num_cards": len(validated.cards),
            "tipos": tipos,
            "cards": data,
        }, ensure_ascii=False)

    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        logger.warning(f"[Tool 2/2] Validación fallida: {errors}")
        return json.dumps({"valid": False, "errors": errors})


# ─────────────────────────────────────────────
# TOOL 3 — Memoria histórica bajo demanda
# ─────────────────────────────────────────────

@tool
def retrieve_memory_context(query: str, top_k: int = 5) -> str:
    """
    Busca memorias históricas relevantes para una consulta concreta (una
    rivalidad, un jugador, un manager...) y devuelve el contexto en texto.

    El prompt ya incluye un contexto histórico general, pero esta tool
    sirve para pedir memorias más específicas sobre algo puntual que vayas
    a escribir en una card (ej. la rivalidad entre dos managers concretos).

    Args:
        query: Texto de búsqueda (ej. "rivalidad Dani Maldinillo", "Mbappé MVP").
        top_k: Número máximo de memorias a devolver (por defecto 5).
    """
    logger.info(f"[Tool 3/3] retrieve_memory_context — query={query!r} top_k={top_k}")

    memories = retrieve_relevant_memories(query, top_k=top_k)
    if not memories:
        return "Sin memorias relevantes encontradas para esa búsqueda."

    return format_memory_context(memories)


# ─────────────────────────────────────────────
# AGENTE
# ─────────────────────────────────────────────

WRITER_AGENT_PROMPT = """
Eres el WriterAgent del periódico fantasy SOTANO LEAGUE.

Recibes un prompt ya construido y debes generar las cards del periódico:

1. generate_cards(prompt)  → llama a Gemini con el prompt recibido
2. validate_cards(result)  → valida el JSON resultante

Si validate_cards devuelve {"valid": false}:
- Llama de nuevo a generate_cards con el mismo prompt
- Vuelve a validar
- Máximo 2 reintentos

Si al escribir una card concreta necesitas más contexto histórico sobre un
jugador, manager o rivalidad puntual (más allá del contexto general que ya
viene incluido en el prompt), llama a retrieve_memory_context(query) en
cualquier momento antes de generar tu respuesta final.

Tu output final es el JSON de cards del campo "cards" devuelto por validate_cards.
""".strip()


def create_writer_agent() -> Agent:
    """
    WriterAgent: recibe un prompt, genera cards, valida y puede pedir
    memoria histórica adicional bajo demanda. El procesamiento de datos
    y la memoria general ya recuperada ocurren fuera, en código Python puro.
    """
    return Agent(
        model=create_gemini_model(),
        system_prompt=WRITER_AGENT_PROMPT,
        tools=[generate_cards, validate_cards, retrieve_memory_context],
    )


def run_writer_agent(prompt: str) -> dict | None:
    """
    Función de conveniencia para llamar al WriterAgent desde run_newspaper.py.

    Usa agent(prompt, structured_output_model=FinalJSON) — NO el método
    Agent.structured_output() aparte, que llama al modelo directamente y se
    salta por completo el bucle de tools del agente (generate_cards,
    validate_cards y retrieve_memory_context nunca se ejecutarían). Pasando
    structured_output_model en la invocación normal, el agente sigue
    pudiendo usar sus tools y, al final, Strands valida la respuesta contra
    el schema sin necesidad de parsear el texto con regex.

    Args:
        prompt: El prompt completo construido por build_final_prompt()

    Returns:
        dict con las cards validadas, o None si falló tras los reintentos.
    """
    agent = create_writer_agent()

    try:
        result = agent(
            f"Genera las cards del periódico con este prompt:\n\n{prompt}",
            structured_output_model=FinalJSON,
        )
    except Exception as e:
        logger.warning(f"[WriterAgent] Ejecución del agente falló: {e}")
        return None

    structured = result.structured_output
    if structured is None:
        logger.warning("[WriterAgent] El agente no produjo structured_output")
        return None

    data = structured.model_dump()
    if not data.get("cards"):
        logger.warning("[WriterAgent] structured_output devolvió cards vacías")
        return None

    logger.info(f"[WriterAgent] {len(data['cards'])} cards extraídas correctamente")
    return data
