from bs4 import BeautifulSoup
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def extraer_subidas_bajadas(html: str) -> pd.DataFrame:
    """
    Parsea una tabla HTML con clase 'thin-scrollbar' y extrae:
      - Nombre del jugador
      - Variación de valor
    Devuelve un DataFrame con columnas ['date', 'nombre', 'variacion'].
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table", class_="thin-scrollbar")

        if not tables:
            logger.warning("No se encontraron tablas 'thin-scrollbar' en el HTML.")
            return pd.DataFrame(columns=["date", "nombre", "variacion"])

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

                    jugadores.append({
                        "date": today,
                        "nombre": nombre,
                        "variacion": variacion
                    })

                except Exception as row_e:
                    logger.debug(f"Error procesando fila de tabla: {row_e}")

        if not jugadores:
            # Distinguir "hoy legítimamente no hay subidas/bajadas" (contenedor
            # presente, 0 filas) de "el selector ya no existe" (mensaje de
            # arriba, líneas 18-20) — antes ambos caían en el mismo except
            # genérico de abajo como un KeyError indistinguible (hallazgo DATA-05).
            logger.warning(
                "Se encontraron tablas 'thin-scrollbar' pero no se extrajo ningún "
                "jugador (0 filas parseadas). Puede que hoy no haya subidas/bajadas, "
                "o que la estructura interna de la fila haya cambiado."
            )
            return pd.DataFrame(columns=["date", "nombre", "variacion"])

        df = pd.DataFrame(jugadores)
        df['variacion'] = df['variacion'].astype(float) / 1_000
        logger.info(f"✅ Extraídos {len(df)} jugadores en subidas/bajadas.")
        return df

    except Exception as e:
        logger.exception(f"❌ Error general en extraer_subidas_bajadas: {e}")
        return pd.DataFrame(columns=["date", "nombre", "variacion"])
