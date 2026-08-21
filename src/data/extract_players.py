"""
extract_players.py — Extrae la base de datos de jugadores desde el HTML de búsqueda de Mister.

Devuelve un DataFrame con: id, nombre, posicion, club, foto_url
"""

import re
import pandas as pd
from bs4 import BeautifulSoup

POSICION_MAP = {
    "1": "Portero",
    "2": "Defensa",
    "3": "Mediocentro",
    "4": "Delantero",
}


def extraer_jugadores(html: str) -> pd.DataFrame:
    """
    Parsea el HTML de la página de búsqueda de jugadores de Mister.

    Args:
        html: Contenido HTML de players_raw.html

    Returns:
        DataFrame con columnas: id, nombre, posicion, club_id, foto_url
    """
    soup = BeautifulSoup(html, "html.parser")
    registros = []

    for li in soup.select("ul.player-list li"):
        try:
            # ── ID del jugador ────────────────────────────────────────────
            avatar_div = li.select_one(".player-avatar[data-id_player]")
            if not avatar_div:
                continue
            player_id = avatar_div.get("data-id_player", "").strip()
            if not player_id:
                continue

            # ── Nombre ────────────────────────────────────────────────────
            name_div = li.select_one(".info .name")
            if not name_div:
                continue
            # Eliminar SVGs y texto extra, quedarnos solo con el texto limpio
            for svg in name_div.find_all("svg"):
                svg.decompose()
            nombre = name_div.get_text(strip=True)

            # ── Posición ──────────────────────────────────────────────────
            pos_div = li.select_one(".player-position[data-position]")
            pos_code = pos_div.get("data-position", "") if pos_div else ""
            posicion = POSICION_MAP.get(pos_code, "Desconocido")

            # ── Club (ID del equipo desde la URL del logo) ────────────────
            team_img = li.select_one("img.team-logo")
            club_id = None
            if team_img:
                src = team_img.get("src", "")
                match = re.search(r"/teams/(\d+)\.png", src)
                if match:
                    club_id = int(match.group(1))

            # ── URL de la foto del jugador ────────────────────────────────
            player_img = avatar_div.select_one("img")
            foto_url = player_img.get("src", "") if player_img else ""

            registros.append({
                "id": player_id,
                "nombre": nombre,
                "posicion": posicion,
                "club_id": club_id,
                "foto_url": foto_url,
            })

        except Exception:
            continue

    df = pd.DataFrame(registros)
    if not df.empty:
        df = df.drop_duplicates(subset=["id"]).reset_index(drop=True)

    return df
