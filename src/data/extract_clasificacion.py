from bs4 import BeautifulSoup
from src.utils.text_cleaning import limpiar_nombre, limpiar_entero, limpiar_dinero
import re
import pandas as pd
import logging

logger = logging.getLogger(__name__)
def _text_of(tag):
    """Helper seguro para extraer texto o '' si tag es None."""
    return tag.get_text(strip=True) if tag else ""

def extraer_clasificaciones(html: str) -> pd.DataFrame:
    """
    Extrae TODAS las clasificaciones del HTML, una por cada jornada (la que tenga 'selected' en cada panel).
    Devuelve un DataFrame con: jornada, nombre, posición, puntos, valor_equipo.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        clasificaciones = []

        paneles = soup.select("div.panel.panel-gameweek")
        if not paneles:
            logger.warning("No se encontraron paneles de jornada en el HTML.")
            return pd.DataFrame(columns=["jornada", "nombre", "posicion", "puntos", "valor_equipo"])

        for panel in paneles:
            selected = panel.select_one("div.gameweek-selector-inline a.btn.btn--secondary.btn--md.selected")
            if not selected:
                continue

            jornada_nombre = selected.get_text(strip=True)
            match = re.findall(r'\d+', jornada_nombre)
            if not match:
                logger.warning(f"No se pudo extraer número de jornada desde '{jornada_nombre}'.")
                continue

            jornada_num = int(match[0])

            lista_jugadores = panel.select_one("ul.player-list.player-list--primary")
            if not lista_jugadores:
                logger.debug(f"Panel de jornada {jornada_num} sin lista de jugadores.")
                continue

            for li in lista_jugadores.find_all("li", recursive=False):
                player_row = li.find("div", class_="player-row")
                if not player_row:
                    continue

                nombre_raw = player_row.find("div", class_="name")
                posicion_raw = player_row.find("div", class_="position")
                puntos_raw = player_row.find("div", class_="points")
                valor_raw = player_row.find("div", class_="played")

                nombre = _text_of(nombre_raw) if nombre_raw else ""
                posicion = limpiar_entero(posicion_raw.text) if posicion_raw else None
                puntos = limpiar_entero(puntos_raw.text) if puntos_raw else None
                valor_equipo = limpiar_dinero(valor_raw.text) if valor_raw else 0

                clasificaciones.append({
                    "jornada": jornada_num,
                    "nombre": nombre,
                    "posicion": posicion,
                    "puntos": puntos,
                    "valor_equipo": valor_equipo
                })

        df = pd.DataFrame(clasificaciones)
        logger.info(f"Clasificaciones extraídas correctamente ({len(df)} registros).")
        return df

    except Exception as e:
        logger.exception(f"Error al extraer clasificaciones: {e}")
        return pd.DataFrame(columns=["jornada", "nombre", "posicion", "puntos", "valor_equipo"])
