import logging
import time
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from src.utils.config_loader import load_config
from src.utils.llm_logger import log_llm_call

logger = logging.getLogger(__name__)

_MODEL_NAME = "gemini-2.5-flash"

# Precios Gemini 2.5 Flash (USD por 1M tokens, texto) — ajustar si cambian.
_PRICE_INPUT_PER_1M = 0.30
_PRICE_OUTPUT_PER_1M = 2.50


def _estimate_cost(prompt_tokens: int | None, completion_tokens: int | None) -> float | None:
    if prompt_tokens is None or completion_tokens is None:
        return None
    return round(
        prompt_tokens / 1_000_000 * _PRICE_INPUT_PER_1M
        + completion_tokens / 1_000_000 * _PRICE_OUTPUT_PER_1M,
        6,
    )

# generate_content() se llama directamente vía el cliente google-genai, sin
# pasar por Strands (que sí reintenta automáticamente las llamadas hechas a
# través de Agent()/structured_output). Sin este retry, un rate limit de
# Gemini (429) durante un backfill de varias jornadas tira el JSON entero.
_RETRYABLE_STATUS_CODES = {429, 500, 503}
_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 5


cfg = load_config()
API_KEY = cfg["env"].get("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("⚠️ GEMINI_API_KEY no encontrado en variables de entorno.")

client = genai.Client(api_key=API_KEY)
response_schema = {
  "type": "OBJECT",
  "properties": {
    "cards": {
      "type": "ARRAY",
      "items": {
        "type": "OBJECT",
        "properties": {
          "tipo": {"type": "STRING"},
          "jugador": {"type": "STRING", "nullable": True},
          "manager": {"type": "STRING", "nullable": True},
          "puntos": {"type": "NUMBER", "nullable": True},
          "dinero": {"type": "NUMBER", "nullable": True},
          "equipo": {"type": "STRING", "nullable": True},
          "titulo": {"type": "STRING"},
          "subtitulo": {"type": "STRING"},
          "texto": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
          }
        },
        "required": ["tipo", "titulo", "subtitulo", "texto"]
      }
    }
  },
  "required": ["cards"]
}
def generate_articles(prompt: str, temperature: float = 0.7) -> dict:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        start = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=_MODEL_NAME,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction="""
                    Eres un periodista deportivo sensacionalista que escribe noticias de una liga fantasy.

                    Devuelve SOLO JSON válido.

                    Reglas:
                    - No texto fuera del JSON
                    - No comentarios
                    - No markdown
                    - No ```json
                    - Respeta exactamente el schema
                    - "texto" SIEMPRE es un array de strings
                    - "puntos" y "dinero" pueden ser null
                    """,
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            usage = getattr(response, "usage_metadata", None)
            prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
            completion_tokens = getattr(usage, "candidates_token_count", None) if usage else None
            total_tokens = getattr(usage, "total_token_count", None) if usage else None

            log_llm_call(
                component="writer_agent.generate_articles",
                provider="gemini",
                model=_MODEL_NAME,
                success=True,
                latency_ms=latency_ms,
                attempt=attempt,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=_estimate_cost(prompt_tokens, completion_tokens),
            )

            return response.parsed  # 🔥 CLAVE

        except genai_errors.APIError as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            log_llm_call(
                component="writer_agent.generate_articles", provider="gemini", model=_MODEL_NAME,
                success=False, latency_ms=latency_ms, attempt=attempt, error=str(e),
            )
            if e.code in _RETRYABLE_STATUS_CODES and attempt < _MAX_ATTEMPTS:
                delay = _BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    f"⏳ Gemini devolvió {e.code} (intento {attempt}/{_MAX_ATTEMPTS}), "
                    f"reintentando en {delay}s..."
                )
                time.sleep(delay)
                continue
            logger.error(f"❌ Error generando JSON tras {attempt} intento(s): {e}")
            return {}

        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            log_llm_call(
                component="writer_agent.generate_articles", provider="gemini", model=_MODEL_NAME,
                success=False, latency_ms=latency_ms, attempt=attempt, error=str(e),
            )
            logger.error(f"❌ Error generando JSON: {e}")
            return {}

    return {}
