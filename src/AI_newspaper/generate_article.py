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

def generate_articles(prompt: str, temperature: float = 0.7) -> str:
    """
    Genera texto usando Google Gemini API.

    Args:
        prompt (str): El prompt de entrada.
        temperature (float): Controla creatividad. Por defecto 0.7.

    Returns:
        str: Texto generado.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction="""
Eres un periodista deportivo muy sensacionalista que escribe sobre las últimas noticias de una liga fantasy privada entre amigos.

DEBES responder EXACTAMENTE en el siguiente formato:

===CLASIFICACION===
FRASE1: ...
FRASE2: ...
FRASE3: ...

===RUMORES===
FRASE: ...

===EVENTOS===
TITULO:
SUBTITULO:
FRASE1:
FRASE2:
(repetido una vez por cada bloque recibido)

No añadas ningún otro texto fuera de estos bloques.
"""
                                   ,
                temperature=temperature
            )
        )
        text = response.text
        logger.info("✅ Texto generado correctamente")
        return text
    except Exception as e:
        logger.error(f"❌ Error generando texto: {e}")
        return ""

def parse_generated_text(texto: str, bloques_info: List[Dict]) -> Dict:
    """
    Convierte el texto generado por el LLM en un JSON estructurado por cards.
    bloques_info: lista con la info de jugador/manager/dinero/puntos antes del prompt
    """

    cards = []

    # --- Clasificación ---
    clasif_match = re.search(r'===CLASIFICACION===\s*(.*?)\s*(?===RUMORES===|$)', texto, re.DOTALL)
    if clasif_match:
        clasif_text = clasif_match.group(1).strip().split("\n")
        cards.append({
            "tipo": "clasificacion",
            "titulo": "CLASIFICACION",
            "subtitulo": "",
            "texto": [line.strip().replace("=", "").replace("FRASE1:", "").replace("FRASE2:", "").replace("FRASE3:", "") for line in clasif_text if line.strip()],
        })

    # --- Rumores ---
    rumor_match = re.search(r'===RUMORES===\s*(.*?)\s*(?===EVENTOS===|$)', texto, re.DOTALL)
    if rumor_match:
        rumor_text = rumor_match.group(1).strip()
        cards.append({
            "tipo": "rumor",
            "titulo": "RUMORES",
            "subtitulo": "",
            "texto": [rumor_text.replace("=", "").replace("-", "").replace("FRASE:", "")],
        })

    # --- Bloques de eventos ---
    eventos_match = re.search(r'===EVENTOS===\s*(.*)', texto, re.DOTALL)
    if eventos_match:
        eventos_text = eventos_match.group(1).strip()

        # Separa cada bloque a partir de "TITULO:"
        bloques_texto = re.split(r'\n(?=TITULO:)', eventos_text)
        for idx, bloque in enumerate(bloques_texto):
            bloque_lines = bloque.strip().split("\n")
            bloque_dict = {
                "tipo": "evento",
                "jugador": "",
                "manager": "",
                "puntos": None,
                "dinero": None,
                "titulo": "",
                "subtitulo": "",
                "texto": []
            }

            if idx < len(bloques_info):
                info = bloques_info[idx]
                bloque_dict.update({
                    "tipo": info.get("evento", ""),
                    "jugador": info.get("jugador", ""),
                    "manager": info.get("manager", ""),
                    "puntos": info.get("puntos"),
                    "dinero": info.get("dinero"),
                    "equipo": info.get("equipo"),
                })

            for line in bloque_lines:
                line = line.strip()
                if line.startswith("TITULO:"):
                    bloque_dict["titulo"] = line.replace("TITULO:", "").strip()
                elif line.startswith("SUBTITULO:"):
                    bloque_dict["subtitulo"] = line.replace("SUBTITULO:", "").strip()
                elif line.startswith("FRASE1:") or line.startswith("FRASE2:"):
                    bloque_dict["texto"].append(line.split(":", 1)[1].strip())

            cards.append(bloque_dict)

    return {"cards": cards}