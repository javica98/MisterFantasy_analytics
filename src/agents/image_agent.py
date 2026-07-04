"""
ImageAgent — Selección inteligente de foto de portada.

Responsabilidad: dado un jugador y su equipo, buscar candidatas en Bing,
evaluarlas y descargar la mejor.

Flujo:
    1. search_candidate_images(jugador, equipo)
       → scraping mejorado de Bing, devuelve hasta 5 URLs válidas
    2. evaluate_images(candidates_json)
       → scoring Python puro por resolución, ratio y tamaño (sin tokens)
       → [DESACTIVADO] evaluate_images_vision: Gemini Vision (reactivar cuando no haya límite de RPM)
    3. download_best_image(evaluation_json, save_path)
       → descarga la imagen con mayor score

Reemplaza a download_player_image() en generate_pdf.py.
"""

import json
import logging
import os
import requests
import numpy as np
from io import BytesIO
from PIL import Image
from strands import Agent, tool
from strands.models.gemini import GeminiModel

from src.utils.config_loader import load_config

logger = logging.getLogger(__name__)

_cfg = load_config()
_GEMINI_API_KEY = _cfg["env"].get("GEMINI_API_KEY")

if not _GEMINI_API_KEY:
    raise ValueError("⚠️ GEMINI_API_KEY no encontrado en variables de entorno.")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/116.0.0.0 Safari/537.36"
}


def create_gemini_model() -> GeminiModel:
    """Crea el modelo Gemini 2.5 Flash para el ImageAgent."""
    return GeminiModel(
        model_id="gemini-2.5-flash",
        client_args={"api_key": _GEMINI_API_KEY},
        params={"temperature": 0.1},
    )


# ─────────────────────────────────────────────
# TOOL 1 — Scraping mejorado de Bing
# ─────────────────────────────────────────────

def _expand_player_name(jugador: str) -> str:
    """
    Si el nombre está abreviado (ej: "K. Mbappé") extrae el apellido completo.
    "K. Mbappé"       -> "Mbappé"
    "T. Lemar"        -> "Lemar"
    "Raphinha"        -> "Raphinha"  (sin cambio)
    "Gavi"            -> "Gavi"      (sin cambio)
    """
    import re
    # Detecta patrón "X. Apellido" o "X.Y. Apellido"
    match = re.match(r'^(?:[A-Z]\.\s*)+(.+)$', jugador.strip())
    if match:
        return match.group(1).strip()
    return jugador


_BAD_DOMAINS = (
    # Redes sociales / plataformas de video
    "ytimg.com", "sndcdn.com", "fbsbx.com", "lookaside.instagram",
    "lookaside.fbsbx", "soundcloud.com", "spotify.com", "tiktok.com",
    "twimg.com",
    # E-commerce
    "amazon.com", "ebay.com", "thegadgetflow.com",
    # Stock photos con marca de agua
    "alamy.com", "gettyimages.com", "shutterstock.com", "istockphoto.com",
    "dreamstime.com", "depositphotos.com", "123rf.com", "stock.adobe.com",
    "pond5.com", "bigstockphoto.com",
)


def _is_bad_url(url: str) -> bool:
    lower = url.lower()
    if any(lower.endswith(ext) for ext in (".gif", ".svg", ".ico", ".webm", ".mp4")):
        return True
    if any(bad in lower for bad in _BAD_DOMAINS):
        return True
    return False


def _bing_candidates(query: str, max_results: int) -> list[str]:
    """
    Scraping de Bing Images usando Playwright (Chromium headless).
    Ejecuta JS real para obtener los murl de los resultados auténticos.
    """
    from playwright.sync_api import sync_playwright

    url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&form=HDRSC2"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)

            murls = page.evaluate(f'''() => {{
                const tags = document.querySelectorAll('a.iusc');
                const urls = [];
                for (const tag of tags) {{
                    try {{
                        const m = JSON.parse(tag.getAttribute('m'));
                        if (m.murl) urls.push(m.murl);
                    }} catch(e) {{}}
                    if (urls.length >= {max_results}) break;
                }}
                return urls;
            }}''')

            browser.close()

        urls = [u for u in murls if not _is_bad_url(u)]
        logger.info(f"[Bing/Playwright] Query '{query[:60]}' -> {len(urls)} URLs")
        return urls

    except Exception as e:
        logger.warning(f"[Bing/Playwright] Error: {e}")
        return []


def _search_candidates(jugador: str, equipo: str) -> str:
    """Lógica pura de búsqueda Bing, sin decorador @tool."""
    logger.info(f"[Tool 1/3] search_candidate_images — {jugador} ({equipo})")

    nombre_busqueda = _expand_player_name(jugador)
    if nombre_busqueda != jugador:
        logger.info(f"[Tool 1/3] Nombre expandido: '{jugador}' -> '{nombre_busqueda}'")

    queries = [
        f"{nombre_busqueda} {equipo} futbolista",
        f"{nombre_busqueda} futbolista LaLiga foto",
        f"{jugador} {equipo} football player",
    ]

    seen = set()
    candidates = []

    for query in queries:
        if len(candidates) >= 8:
            break
        for img_url in _bing_candidates(query, max_results=12):
            if img_url in seen:
                continue
            seen.add(img_url)
            if _is_bad_url(img_url):
                continue
            candidates.append(img_url)
            logger.info(f"[Tool 1/3] Candidata {len(candidates)}: {img_url[:80]}...")
            if len(candidates) >= 8:
                break

    logger.info(f"[Tool 1/3] OK — {len(candidates)} candidatas encontradas")
    return json.dumps({"candidates": candidates, "jugador": jugador, "equipo": equipo})


@tool
def search_candidate_images(jugador: str, equipo: str) -> str:
    """
    Busca imágenes del jugador en Bing y devuelve hasta 8 URLs candidatas.
    Maneja nombres abreviados (ej: "K. Mbappé") expandiéndolos al apellido.
    NO hace peticiones HEAD (poco fiable en CDNs de imágenes).
    Llama a esta tool PRIMERO.

    Args:
        jugador: Nombre del jugador (ej: "Bellingham" o "K. Mbappé")
        equipo: Equipo real del jugador (ej: "Real Madrid")
    """
    return _search_candidates(jugador, equipo)


# ─────────────────────────────────────────────
# CLIP — Clasificador zero-shot "¿hay un futbolista?"
# ─────────────────────────────────────────────

_clip_model = None  # cargado lazy la primera vez

_CLIP_POSITIVE = "a professional football player portrait photo"
_CLIP_NEGATIVE = "a stadium crowd logo badge field grass"

def _get_clip_model():
    """Carga el modelo CLIP una sola vez y lo cachea en memoria."""
    global _clip_model
    if _clip_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("[CLIP] Cargando modelo clip-ViT-B-32 (primera vez ~350MB)...")
        _clip_model = SentenceTransformer("clip-ViT-B-32")
        logger.info("[CLIP] Modelo cargado.")
    return _clip_model


def _clip_footballer_score(img: Image.Image) -> tuple[float, str]:
    """
    Clasifica si una imagen contiene un futbolista profesional usando CLIP zero-shot.

    Calcula la similitud coseno entre el embedding de la imagen y el texto
    ``"a professional football player portrait photo"``.

    Args:
        img: Imagen PIL a clasificar (cualquier modo, se convierte a RGB internamente).

    Returns:
        Tupla ``(puntos, razón)``:
        - ``(3.0, "CLIP futbolista (0.27)")``      si similitud >= 0.26
        - ``(2.0, "CLIP probable futbolista ...")`` si similitud >= 0.22
        - ``(1.0, "CLIP posible futbolista ...")``  si similitud >= 0.18
        - ``(0.0, "CLIP no futbolista (0.14)")``    si similitud < 0.18
        - ``(0.0, "CLIP error")``                   si falla la inferencia

    Note:
        El modelo CLIP se carga lazy en ``_clip_model`` la primera vez que se
        invoca (``~350MB``, ``~2s``). Las siguientes llamadas reutilizan el
        modelo en memoria.
    """
    try:
        model = _get_clip_model()
        img_emb = model.encode(img.convert("RGB"))
        pos_emb = model.encode(_CLIP_POSITIVE)
        neg_emb = model.encode(_CLIP_NEGATIVE)

        # Similitud coseno manual (numpy)
        def cos_sim(a, b):
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

        sim_pos = cos_sim(img_emb, pos_emb)
        sim_neg = cos_sim(img_emb, neg_emb)
        # Usamos la similitud positiva; el negativo sirve como referencia de log
        logger.debug(f"[CLIP] sim_futbolista={sim_pos:.3f} sim_otro={sim_neg:.3f}")

        if sim_pos >= 0.26:
            return 3.0, f"CLIP futbolista ({sim_pos:.2f})"
        elif sim_pos >= 0.22:
            return 2.0, f"CLIP probable futbolista ({sim_pos:.2f})"
        else:
            return 0.0, f"CLIP no futbolista ({sim_pos:.2f})"
    except Exception as e:
        logger.warning(f"[CLIP] Error al evaluar imagen: {e}")
        return 0.0, "CLIP error"


# ─────────────────────────────────────────────
# TOOL 2 — Evaluación Python puro + CLIP (activa)
# ─────────────────────────────────────────────
# Scoring: resolución, ratio, tamaño de archivo + CLIP "¿es un futbolista?"
# Preferimos imágenes verticales (buenas para portada) y de alta resolución.

def _evaluate_candidates(candidates_json: str) -> str:
    """Lógica pura de evaluación, sin decorador @tool."""
    logger.info("[Tool 2/3] evaluate_images — scoring Python puro (sin tokens)")

    data = json.loads(candidates_json)
    candidates = data.get("candidates", [])

    if not candidates:
        return json.dumps({"error": "No hay candidatas para evaluar", "best_url": None, "scores": []})

    scores = []

    for i, url in enumerate(candidates):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            if resp.status_code != 200:
                scores.append({"url": url, "score": 0, "reason": "No se pudo descargar"})
                continue

            img_bytes = resp.content
            file_size = len(img_bytes)

            img = Image.open(BytesIO(img_bytes))
            w, h = img.size
            total_pixels = w * h

            score = 0.0
            reasons = []

            # Resolución (hasta 4 pts)
            if total_pixels >= 1_000_000:    # >= 1MP
                score += 4
                reasons.append("alta resolución")
            elif total_pixels >= 500_000:
                score += 2.5
                reasons.append("resolución media")
            elif total_pixels >= 200_000:
                score += 1
                reasons.append("resolución baja")

            # Ratio vertical (2 pts)
            if h > w:
                score += 2
                reasons.append("formato vertical")
            elif h == w:
                score += 1
                reasons.append("formato cuadrado")

            # Tamaño de archivo (hasta 2 pts)
            if file_size >= 200_000:         # >= 200KB
                score += 2
                reasons.append("archivo grande")
            elif file_size >= 80_000:
                score += 1
                reasons.append("archivo medio")

            # Formato válido (2 pts)
            if img.format in ("JPEG", "PNG", "WEBP"):
                score += 2

            # CLIP: ¿parece un futbolista? — filtro duro: si score=0 se descarta
            clip_pts, clip_reason = _clip_footballer_score(img)
            reasons.append(clip_reason)
            if clip_pts == 0.0:
                logger.info(f"[Tool 2/3] Candidata {i+1}: DESCARTADA — {clip_reason} ({w}x{h})")
                scores.append({"url": url, "score": 0, "reason": f"DESCARTADA: {clip_reason}"})
                continue
            score += clip_pts * 3  # mayor peso al criterio futbolista

            reason = ", ".join(reasons) if reasons else "sin destacar"
            scores.append({"url": url, "score": round(score, 1), "reason": reason})
            logger.info(f"[Tool 2/3] Candidata {i+1}: score={score:.1f} ({w}x{h}) — {reason}")

        except Exception as e:
            logger.warning(f"[Tool 2/3] Error evaluando candidata {i+1}: {e}")
            scores.append({"url": url, "score": 0, "reason": f"Error: {e}"})

    scores.sort(key=lambda x: x["score"], reverse=True)
    best = scores[0] if scores and scores[0]["score"] > 0 else None

    if best:
        logger.info(f"[Tool 2/3] Mejor: score={best['score']} — {best['reason']}")
    else:
        logger.warning("[Tool 2/3] Sin candidatas validas con futbolista detectado por CLIP")

    return json.dumps({
        "best_url": best["url"] if best else None,
        "best_score": best["score"] if best else 0,
        "scores": scores,
    })


@tool
def evaluate_images(candidates_json: str) -> str:
    """
    Evalúa cada imagen candidata con criterios de calidad y asigna un score 0-10.
    Llama a esta tool DESPUÉS de search_candidate_images.

    Criterios:
    - Resolución total (píxeles): más grande = mejor (hasta 4 pts)
    - Ratio vertical (alto > ancho): preferible para portada (2 pts)
    - Tamaño de archivo: más peso = más detalle (hasta 2 pts)
    - Formato válido (jpg/png/webp): (2 pts)
    - CLIP zero-shot "¿hay un futbolista?": (hasta 3 pts)
    Score máximo: 13 pts. Evalúa hasta 8 candidatas.

    Args:
        candidates_json: JSON devuelto por search_candidate_images.
    """
    return _evaluate_candidates(candidates_json)


# ─────────────────────────────────────────────
# TOOL 2b — Evaluación con Gemini Vision (DESACTIVADA)
# ─────────────────────────────────────────────
# Reactivar cuando no haya límite de RPM o se use tier de pago.
# Para activar: sustituir evaluate_images por evaluate_images_vision
# en create_image_agent() y en IMAGE_AGENT_PROMPT.
#
# def evaluate_images_vision(candidates_json: str) -> str:
#     """
#     Evalúa cada imagen candidata con Gemini Vision y asigna un score 0-10.
#     REQUIERE llamadas a Gemini — desactivada por límite de RPM en free tier.
#     """
#     from google import genai
#     from google.genai import types
#
#     data = json.loads(candidates_json)
#     candidates = data.get("candidates", [])
#     jugador = data.get("jugador", "el jugador")
#     client = genai.Client(api_key=_GEMINI_API_KEY)
#     scores = []
#
#     for i, url in enumerate(candidates):
#         try:
#             resp = requests.get(url, headers=_HEADERS, timeout=10)
#             img_bytes = resp.content
#             content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
#             if content_type not in ["image/jpeg", "image/png", "image/webp"]:
#                 content_type = "image/jpeg"
#
#             response = client.models.generate_content(
#                 model="gemini-2.5-flash",
#                 contents=[
#                     types.Part.from_bytes(data=img_bytes, mime_type=content_type),
#                     f"""Evalúa esta imagen para portada de periódico deportivo fantasy.
# Jugador: {jugador}. Puntúa 0-10: jugador solo (3pts), cara visible (2pts),
# fondo limpio (2pts), formato vertical (1pt), resolución (2pts).
# Responde SOLO: {{"score": <n>, "reason": "<frase>"}}"""
#                 ],
#             )
#             result = json.loads(response.text.strip())
#             scores.append({"url": url, "score": float(result.get("score", 0)),
#                           "reason": result.get("reason", "")})
#         except Exception as e:
#             scores.append({"url": url, "score": 0, "reason": str(e)})
#
#     scores.sort(key=lambda x: x["score"], reverse=True)
#     best = scores[0] if scores else None
#     return json.dumps({"best_url": best["url"] if best else None,
#                       "best_score": best["score"] if best else 0, "scores": scores})


# ─────────────────────────────────────────────
# TOOL 3 — Descarga de la imagen ganadora
# ─────────────────────────────────────────────

def _download_best(evaluation_json: str, save_path: str) -> str:
    """Lógica pura de descarga, sin decorador @tool."""
    logger.info(f"[Tool 3/3] download_best_image → {save_path}")

    data = json.loads(evaluation_json)
    best_url = data.get("best_url")
    best_score = data.get("best_score", 0)

    if not best_url:
        return json.dumps({"success": False, "error": "No hay URL válida para descargar"})

    logger.info(f"[Tool 3/3] Descargando mejor candidata (score: {best_score}/10)")

    try:
        resp = requests.get(best_url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()

        image = Image.open(BytesIO(resp.content)).convert("RGB")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        image.save(save_path, "JPEG", quality=95)

        logger.info(f"[Tool 3/3] OK — guardada en {save_path} (score: {best_score}/10)")
        return json.dumps({"success": True, "path": save_path, "score": best_score})

    except Exception as e:
        logger.error(f"[Tool 3/3] Error: {e}")
        return json.dumps({"success": False, "error": str(e)})


@tool
def download_best_image(evaluation_json: str, save_path: str) -> str:
    """
    Descarga la imagen con mejor score y la guarda en save_path.
    Llama a esta tool DESPUÉS de evaluate_images.

    Args:
        evaluation_json: JSON devuelto por evaluate_images.
        save_path: Ruta completa donde guardar la imagen.
    """
    return _download_best(evaluation_json, save_path)


# ─────────────────────────────────────────────
# AGENTE
# ─────────────────────────────────────────────

IMAGE_AGENT_PROMPT = """
Eres el ImageAgent del periódico fantasy SOTANO LEAGUE.

Encuentra y descarga la mejor foto de portada siguiendo este flujo:

1. search_candidate_images(jugador, equipo) → busca candidatas en Bing
2. evaluate_images(candidates_json)         → puntúa por calidad técnica
3. download_best_image(evaluation_json, save_path) → descarga la mejor

Tu output final es el resultado de download_best_image.
""".strip()


def create_image_agent() -> Agent:
    """ImageAgent: busca, evalúa (Python puro) y descarga la mejor foto."""
    return Agent(
        model=create_gemini_model(),
        system_prompt=IMAGE_AGENT_PROMPT,
        tools=[search_candidate_images, evaluate_images, download_best_image],
    )


def run_image_agent(jugador: str, equipo: str, save_path: str) -> bool:
    """
    Usa el ImageAgent con Gemini para buscar, evaluar y descargar la mejor foto.
    Para el batch sin LLM, usar run_image_pipeline().
    """
    import re

    agent = create_image_agent()
    response = agent(
        f"Busca y descarga la mejor foto de {jugador} ({equipo}) "
        f"y guárdala en: {save_path}"
    )

    response_str = str(response)
    match = re.search(r'\{"success":\s*(true|false)[^}]*\}', response_str)
    if match:
        try:
            result = json.loads(match.group(0))
            return result.get("success", False)
        except json.JSONDecodeError:
            pass

    return os.path.exists(save_path)


def run_image_pipeline(jugador: str, equipo: str, save_path: str) -> bool:
    """
    Versión sin LLM: llama las 3 funciones directamente sin pasar por Gemini.
    Usar para batch processing donde no se necesita el agente.
    """
    try:
        candidates_json = _search_candidates(jugador, equipo)
        evaluation_json = _evaluate_candidates(candidates_json)
        result_json = _download_best(evaluation_json, save_path)
        result = json.loads(result_json)
        return result.get("success", False)
    except Exception as e:
        logger.error(f"[Pipeline] Error: {e}")
        return os.path.exists(save_path)
