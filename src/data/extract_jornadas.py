from bs4 import BeautifulSoup
import re
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def extraer_jornadas(html: str) -> pd.DataFrame:
    """
    Extrae el listado de jornadas futuras o pasadas del HTML.

    Retorna un DataFrame con columnas:
      - date: fecha de extracción
      - jornada: número de jornada
      - detalles: texto del estado (ej. 'Finalizada', 'En juego', etc.)
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        resultados = []

        # Contenedor de jornadas
        nav = soup.find("div", class_="nav thin-scrollbar")
        if not nav:
            logger.warning("No se encontró el contenedor de jornadas en el HTML.")
            return pd.DataFrame(resultados)

        # Buscar enlaces de jornadas
        for a in nav.find_all("a", class_=lambda x: x and "gameweek" in x):
            # Extraer número de jornada
            nombre_jornada = a.find("div", class_="gameweek__name")
            jornada = None
            if nombre_jornada:
                match = re.search(r"\d+", nombre_jornada.get_text(strip=True))
                if match:
                    jornada = int(match.group())

            # Extraer detalles de estado
            status_div = a.find("div", class_="gameweek__status")
            detalles = status_div.get_text(strip=True) if status_div else ""
            detalles = re.sub(r"\s+", " ", detalles)

            # Fecha actual (normalizada)
            today = pd.Timestamp.today().normalize()

            if jornada is not None:
                resultados.append({
                    "date": today,
                    "jornada": jornada,
                    "detalles": detalles
                })
        
        logger.info(f"Extraídas {len(resultados)} jornadas correctamente.")
        return pd.DataFrame(resultados)

    except Exception as e:
        logger.exception(f"Error al extraer jornadas: {e}")
        return pd.DataFrame()
