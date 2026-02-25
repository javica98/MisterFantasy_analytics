import logging
from google import genai
from google.genai import types
import os
from src.utils.config_loader import load_config
import re
from typing import List, Dict

logger = logging.getLogger(__name__)


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

    except Exception as e:
        logger.error(f"❌ Error generando JSON: {e}")
        return {}