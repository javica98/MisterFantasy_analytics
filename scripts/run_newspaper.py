import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Ajuste de entorno ─────────────────────────────────────────────────────────
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent
SRC_DIR = ROOT_DIR / "src"

for p in (ROOT_DIR, SRC_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.chdir(ROOT_DIR)


from src.AI_newspaper.generate_json import generate_json
from src.AI_newspaper.generate_prompt import generate_prompts,build_final_prompt
from src.AI_newspaper.generate_pdf import create_pdf
from src.agents.orchestrator_agent import run_orchestrator
from src.memory.embedding_store import build_memory_query, rebuild_embedding_index
from src.memory.memory_builder import build_memories
from src.memory.memory_store import DEFAULT_MEMORY_PATH, format_memory_context, retrieve_relevant_memories, upsert_memories
# --- Cargar configuración ---
from src.utils.config_loader import load_config
from src.utils.data_utils import normalize_date_column
from src.utils.file_utils import safe_read_html, safe_read_csv,safe_read_json, safe_save_csv,safe_save_json,safe_read_text, safe_save_text,safe_save_png


cfg = load_config()

# --- Configurar logging ---
log_level = getattr(logging, cfg.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
log_file = cfg.get("logging", {}).get("file", "logs/app.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.debug("Directorio raíz: %s", ROOT_DIR)

# --- Asegurar directorios base ---
os.makedirs(cfg["data"]["raw_dir"], exist_ok=True)
os.makedirs(cfg["data"]["processed_dir"], exist_ok=True)

# Directorios base
DATA_RAW = cfg["data"]["raw_dir"]
DATA_PROCESSED = cfg["data"]["processed_dir"]

# Archivos HTML
HTML_AUX = cfg["paths"]["html"]["aux"]
HTML_CLAS_AUX = cfg["paths"]["html"]["clas_aux"]
HTML_MERCADO_AUX = cfg["paths"]["html"]["mercado"]
HTML_JORNADAS_AUX = cfg["paths"]["html"]["jornadas"]
HTML_SUBIDASBAJADAS = cfg["paths"]["html"]["subidas_bajadas"]
HTML_GAMEWEEK = cfg["paths"]["html"]["gameweek"]
HTML_QUINIELAS = cfg["paths"]["html"]["quiniela"]

# Archivos CSV
CSV_NOTIFICACIONES = cfg["paths"]["csv"]["notificaciones"]
CSV_NOTIFICACIONES_CLEAN = cfg["paths"]["csv"]["notificaciones_clean"]
CSV_CLASIFICACIONES = cfg["paths"]["csv"]["clasificaciones"]
CSV_MERCADO = cfg["paths"]["csv"]["mercado"]
CSV_JORNADA = cfg["paths"]["csv"]["jornada"]
CSV_SUBIDASBAJADAS = cfg["paths"]["csv"]["subidas_bajadas"]
CSV_GAMEWEEK = cfg["paths"]["csv"]["gameweek"]
CSV_QUINIELAS = cfg["paths"]["csv"]["quiniela"]

# Archivos CSV
JSON_NEWS = cfg["paths"]["json"]["news"]
NEWS_UTILS = cfg["paths"]["images"]["news_utils"]

#PHOTOS
IMAGES_TEAMS_DIR = cfg["paths"]["images"]["teams_dir"]
DEFAULT_TEAM_IMAGE = cfg["paths"]["images"]["default_team"]
NEWS_UTILS = cfg["paths"]["images"]["news_utils"]
IMG_NEWS = cfg["paths"]["images"]["news"]

# Variables de entorno (login)
MISTER_USERNAME = cfg["env"]["MISTER_USERNAME"]
MISTER_PASSWORD = cfg["env"]["MISTER_PASSWORD"]
MISTER_BASE_URL = cfg["env"]["MISTER_BASE_URL"]
fecha_hoy = datetime.today().strftime("%Y-%m-%d")
# --- 1. Create JSONs ---
logger.info("Creando Jsons...")
csv_gameweek = safe_read_csv(CSV_GAMEWEEK)
csv_notificaciones = safe_read_csv(CSV_NOTIFICACIONES_CLEAN)
csv_clasificacion = safe_read_csv(CSV_CLASIFICACIONES)
csv_quinielas = safe_read_csv(CSV_QUINIELAS)

if csv_gameweek is None or csv_notificaciones is None:
    logger.error("CSVs de gameweek o notificaciones no encontrados. Abortando.")
    sys.exit(1)

if csv_clasificacion is None or csv_quinielas is None:
    logger.error("CSVs de clasificacion o quinielas no encontrados. Abortando.")
    sys.exit(1)

daily_json = generate_json(
    3,
    csv_notificaciones[csv_notificaciones["type"] == "transfer"],
    csv_gameweek,
    csv_clasificacion,
    csv_quinielas,
)

n_transfers = len(daily_json.get("transfers", []))
n_gameweek = len(daily_json.get("gameweek", []))

if n_transfers == 0 and n_gameweek == 0:
    logger.error(
        "No hay transfers ni gameweek en los ultimos 3 dias. "
        "Comprueba que los datos esten actualizados o amplia el rango de dias."
    )
    sys.exit(1)

if n_transfers == 0:
    logger.warning("Sin transfers en los ultimos 3 dias — el periodico no tendra noticias de mercado.")
if n_gameweek == 0:
    logger.warning("Sin gameweek en los ultimos 3 dias — el periodico no tendra MVPs ni resultados.")

logger.info("Json creado: %d transfers, %d entradas de gameweek.", n_transfers, n_gameweek)
json_final_path = os.path.join(JSON_NEWS, "articles", "news_json.json")
daily_json = safe_save_json(daily_json, json_final_path)
    
# --- 2. Crear prompt ---
logger.info("Creando prompt...")
json_new = safe_read_json(json_final_path)
if (json_new is None):
    logger.warning("⏭️ Saltando prompt .json no existe.")
else:
    prompt_json = generate_prompts(json_new)
    memory_query = build_memory_query(json_new)
    relevant_memories = retrieve_relevant_memories(memory_query, top_k=8)
    memory_context = format_memory_context(relevant_memories)
    logger.info("🧠 Memoria recuperada para el prompt: %s recuerdos.", len(relevant_memories))
    commun_prompt_json = build_final_prompt(prompt_json["bloques"],json_new,memory_context)
    logger.info("✅ Prompt Json creado.")
    prompt_final_path = os.path.join(JSON_NEWS, "prompts", "news_prompt.txt")
    prompt_saved = safe_save_text(commun_prompt_json,prompt_final_path)

# --- 3. Orquestador: genera cards + descarga fotos de portada ---
prompt_txt = safe_read_text(prompt_final_path)

# Determinar jugadores de portada (misma lógica que create_pdf)
from src.AI_newspaper.generate_pdf import get_cards_by_tipo
cards_preview = safe_read_json(json_final_path)  # usamos el json para preview
# Leer prompt_json para obtener los bloques
prompt_json_data = generate_prompts(json_new)
fichajes_cards = [b for b in prompt_json_data["bloques"] if b["evento"] == "Fichaje destacado"]
mvp_cards = [b for b in prompt_json_data["bloques"] if b["evento"] == "MVP de la jornada"]

portada_fichajes = fichajes_cards[0] if fichajes_cards else mvp_cards[0] if mvp_cards else {"jugador": "", "equipo": ""}
portada_jornada = mvp_cards[0] if mvp_cards else fichajes_cards[0] if fichajes_cards else {"jugador": "", "equipo": ""}

path_foto_fichajes = os.path.join(NEWS_UTILS, "Portada_Fichajes.jpg")
path_foto_jornada = os.path.join(NEWS_UTILS, "Portada_Jornada.jpg")

logger.info("📡 Llamando al OrchestratorAgent...")
texto_generado = run_orchestrator(
    prompt=prompt_txt,
    portada_fichajes=portada_fichajes,
    portada_jornada=portada_jornada,
    path_fichajes=path_foto_fichajes,
    path_jornada=path_foto_jornada,
)

if texto_generado is None:
    logger.error("❌ OrchestratorAgent no pudo generar cards válidas.")
    sys.exit(1)

logger.info("✅ Todo el contenido creado.")
cards_json_path = os.path.join(JSON_NEWS, "cards", "news_cards.json")
json_weekly_path = os.path.join(JSON_NEWS, "articles", f"{fecha_hoy}_json.json")
article = safe_save_json(texto_generado,cards_json_path)
article = safe_save_json(texto_generado,json_weekly_path)

# --- 3.1 Actualizar memoria historica para el futuro RAG ---
memories = build_memories(json_new, texto_generado)
changed_memories = upsert_memories(memories, DEFAULT_MEMORY_PATH)
logger.info("🧠 Memoria actualizada: %s recuerdos (%s nuevos/actualizados).", len(memories), changed_memories)
if changed_memories:
    rebuild_embedding_index()
    logger.info("🧠 Índice vectorial de memoria reconstruido.")

#--- 4.Crear Pdf
json= safe_read_json(json_final_path)
clasificacion_json= json["clasificacion"]
quiniela_json= json["quinielas"]
cards = safe_read_json(cards_json_path)
portada_fichajes = create_pdf("Fichajes",cards,quiniela_json,NEWS_UTILS,IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
portada_jornada = create_pdf("Jornada",cards,clasificacion_json,NEWS_UTILS,IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
fecha_hoy = datetime.today().strftime("%Y-%m-%d")
portada_fichajes_path = os.path.join(IMG_NEWS, f"{fecha_hoy}_fichajes_news.png")
portada_jornada_path = os.path.join(IMG_NEWS, f"{fecha_hoy}_jornada_news.png")
card_save = safe_save_png(portada_fichajes,portada_fichajes_path)
card_save = safe_save_png(portada_jornada,portada_jornada_path)
logger.info("🏁 Proceso de extracción completado sin errores.")


