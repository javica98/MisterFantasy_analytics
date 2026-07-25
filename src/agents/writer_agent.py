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

Tu output final es el JSON de cards del campo "cards" devuelto por validate_cards.
""".strip()


def create_writer_agent() -> Agent:
    """
    WriterAgent simplificado: recibe un prompt, genera cards, valida.
    Todo el procesamiento de datos ocurre fuera, en código Python puro.
    """
    return Agent(
        model=create_gemini_model(),
        system_prompt=WRITER_AGENT_PROMPT,
        tools=[generate_cards, validate_cards],
    )


def run_writer_agent(prompt: str) -> dict | None:
    """
    Función de conveniencia para llamar al WriterAgent desde run_newspaper.py.

    Usa Agent.structured_output(FinalJSON, ...) para que Strands devuelva
    directamente un objeto validado por Pydantic, en vez de tener que
    extraer el JSON del texto de respuesta con regex.

    Args:
        prompt: El prompt completo construido por build_final_prompt()

    Returns:
        dict con las cards validadas, o None si falló tras los reintentos.
    """
    agent = create_writer_agent()

    try:
        result = agent.structured_output(
            FinalJSON,
            f"Genera las cards del periódico con este prompt:\n\n{prompt}",
        )
    except Exception as e:
        logger.warning(f"[WriterAgent] structured_output falló: {e}")
        return None

    data = result.model_dump()
    if not data.get("cards"):
        logger.warning("[WriterAgent] structured_output devolvió cards vacías")
        return None

    logger.info(f"[WriterAgent] {len(data['cards'])} cards extraídas correctamente")
    return data
