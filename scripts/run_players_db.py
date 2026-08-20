"""
run_players_db.py — Genera/actualiza la base de datos de jugadores.

Lee el HTML de búsqueda de jugadores (data/raw/players_raw.html),
extrae nombre, posición, club y URL de foto, y guarda en:
    data/processed/jugadores.csv

El CSV se actualiza de forma incremental: los jugadores nuevos se añaden
y los existentes se actualizan si hay cambios.

Ejecutar:
    python scripts/run_players_db.py
"""

import os
import sys
import logging
from pathlib import Path

import pandas as pd

# ── Ajuste de rutas ──────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from src.data.extract_players import extraer_jugadores
from src.AI_newspaper.generate_json import TEAM_MAP
from src.utils.config_loader import load_config
from src.utils.file_utils import safe_read_html, safe_read_csv, safe_save_csv

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

cfg = load_config(validate_env=False)

HTML_PATH = cfg["paths"]["html"].get("players", "data/raw/players_raw.html")
CSV_PATH  = cfg["paths"]["csv"]["jugadores"]


def main():
    # ── 1. Leer HTML ─────────────────────────────────────────────────────────
    logger.info("Leyendo HTML de jugadores...")
    html = safe_read_html(HTML_PATH)
    if html is None:
        logger.error("❌ No se encontró %s", HTML_PATH)
        sys.exit(1)

    # ── 2. Extraer jugadores ─────────────────────────────────────────────────
    logger.info("Extrayendo jugadores...")
    df_new = extraer_jugadores(html)

    if df_new.empty:
        logger.error("❌ No se extrajeron jugadores. Revisa la estructura del HTML.")
        sys.exit(1)

    logger.info("✅ %d jugadores extraídos del HTML.", len(df_new))

    # ── 3. Mapear club_id → nombre del club ──────────────────────────────────
    df_new["club"] = df_new["club_id"].map(lambda x: TEAM_MAP.get(x, str(x)) if x else "")
    df_new = df_new.drop(columns=["club_id"])

    # ── 4. Merge con CSV existente ───────────────────────────────────────────
    df_existing = safe_read_csv(CSV_PATH)

    if df_existing is not None and not df_existing.empty:
        # Actualizar jugadores existentes y añadir nuevos
        df_existing = df_existing.set_index("id")
        df_new_indexed = df_new.set_index("id")

        # Los nuevos sobreescriben los existentes (por si cambia club/foto)
        df_merged = df_new_indexed.combine_first(df_existing)
        # Pero los nuevos tienen prioridad en las columnas que traen
        df_merged.update(df_new_indexed)
        df_final = df_merged.reset_index()

        nuevos = len(df_new_indexed) - len(df_new_indexed.index.intersection(df_existing.index))
        actualizados = len(df_new_indexed.index.intersection(df_existing.index))
        logger.info("📊 %d nuevos jugadores, %d actualizados.", nuevos, actualizados)
    else:
        df_final = df_new
        logger.info("📊 CSV nuevo creado con %d jugadores.", len(df_final))

    # ── 5. Guardar ───────────────────────────────────────────────────────────
    # Ordenar por posición y nombre
    orden_posicion = {"Portero": 1, "Defensa": 2, "Mediocentro": 3, "Delantero": 4}
    df_final["_orden"] = df_final["posicion"].map(orden_posicion).fillna(5)
    df_final = df_final.sort_values(["_orden", "nombre"]).drop(columns=["_orden"])

    safe_save_csv(df_final, CSV_PATH)
    logger.info("✅ Base de datos guardada en %s (%d jugadores total).", CSV_PATH, len(df_final))


if __name__ == "__main__":
    main()
