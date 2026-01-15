from bs4 import BeautifulSoup
import pandas as pd
import re
import logging

logger = logging.getLogger(__name__)

def limpiar_entero(txt):
    if not txt:
        return None
    m = re.findall(r"\d+", txt)
    return int(m[0]) if m else None


def extraer_quinielas(html: str) -> pd.DataFrame:
    """
    Extrae la quinieala:
    jornada, nombre, posicion, puntos
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # -------------------------------------------------
        # 1️⃣ Extraer jornada
        # -------------------------------------------------
        jornada = None
        selector = soup.select_one("div.pool-gw-selector option[selected]")
        if selector:
            txt = selector.get_text(" ", strip=True)   # "Jornada 20 • 0 aciertos"
            m = re.findall(r"\d+", txt)
            if m:
                jornada = int(m[0])

        if not jornada:
            logger.warning("No se pudo detectar la jornada")

        # -------------------------------------------------
        # 2️⃣ Lista de jugadores
        # -------------------------------------------------
        lista = soup.select_one("ul.pool-table.player-list.player-list--primary")
        if not lista:
            logger.warning("No se encontró la lista de quinielas")
            return pd.DataFrame(columns=["jornada", "nombre", "posicion", "puntos"])

        filas = []

        for li in lista.find_all("li", recursive=False):
            row = li.select_one("div.player-row a.user")
            if not row:
                continue

            nombre = row.get("data-name", "").strip()

            pos_raw = row.select_one("div.position")
            puntos_raw = row.select_one("div.points")

            posicion = limpiar_entero(pos_raw.text if pos_raw else "")
            puntos = limpiar_entero(puntos_raw.text if puntos_raw else "")

            filas.append({
                "jornada": jornada,
                "nombre": nombre,
                "posicion": posicion,
                "puntos": puntos
            })

        df = pd.DataFrame(filas)
        logger.info(f"Clasificación extraída ({len(df)} jugadores, jornada {jornada})")
        return df

    except Exception as e:
        logger.exception(f"Error al extraer clasificación pool: {e}")
        return pd.DataFrame(columns=["jornada", "nombre", "posicion", "puntos"])
