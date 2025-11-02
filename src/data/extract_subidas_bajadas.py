from bs4 import BeautifulSoup
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def extraer_subidas_bajadas(html: str) -> pd.DataFrame:
    """
    Parsea una tabla HTML con clase 'thin-scrollbar' y extrae:
      - Nombre del jugador
      - Variación de valor
      - Signo (subida/bajada)
    Devuelve un DataFrame con columnas ['date', 'nombre', 'variacion', 'signo'].
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table", class_="thin-scrollbar")

        if not tables:
            logger.warning("No se encontraron tablas 'thin-scrollbar' en el HTML.")
            return pd.DataFrame(columns=["date", "nombre", "variacion", "signo"])

        jugadores = []
        today = pd.Timestamp.today().normalize()

        for table in tables:
            for tr in table.find_all("tr"):
                try:
                    # Nombre del jugador
                    a_tag = tr.find("a", class_="btn btn-sw-link")
                    nombre = a_tag.get_text(strip=True) if a_tag else None
                    if not nombre:
                        continue

                    # Variación de valor
                    td_valor = tr.find("td", class_=["td-right", "green", "red"])
                    if not td_valor:
                        continue

                    variacion = td_valor.get_text(strip=True)
                    clase = td_valor.get("class", [])
                    signo = "sube" if "green" in clase else "baja" if "red" in clase else None

                    jugadores.append({
                        "date": today,
                        "nombre": nombre,
                        "variacion": variacion,
                        "signo": signo
                    })

                except Exception as row_e:
                    logger.debug(f"Error procesando fila de tabla: {row_e}")

        df = pd.DataFrame(jugadores)
        logger.info(f"✅ Extraídos {len(df)} jugadores en subidas/bajadas.")
        return df

    except Exception as e:
        logger.exception(f"❌ Error general en extraer_subidas_bajadas: {e}")
        return pd.DataFrame(columns=["date", "nombre", "variacion", "signo"])
