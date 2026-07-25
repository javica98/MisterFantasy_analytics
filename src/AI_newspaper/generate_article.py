import logging
import time
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
import os
from src.utils.config_loader import load_config
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

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
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
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

            return response.parsed  # 🔥 CLAVE

        except genai_errors.APIError as e:
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
            logger.error(f"❌ Error generando JSON: {e}")
            return {}

    return {}