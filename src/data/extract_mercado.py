from bs4 import BeautifulSoup
import re
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def extraer_mercado(html: str) -> pd.DataFrame:
    """
    Extrae el listado del mercado de jugadores en venta desde el HTML.

    Devuelve un DataFrame con columnas:
      - date, manager, periodo, jugador, precio,
        posicionJugador, puntosJugador, equipoLiga,
        avgPoints, estado
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        wrapper = soup.find("div", class_="wrapper wrapper--spaced")
        if not wrapper:
            logger.warning("No se encontró el contenedor principal del mercado.")
            return pd.DataFrame()

        lista_jugadores = wrapper.find("ul", id="list-on-sale")
        if not lista_jugadores:
            logger.info("No hay jugadores actualmente en venta.")
            return pd.DataFrame()

        mercado = []
        today = pd.Timestamp.today().normalize()

        for item in lista_jugadores.find_all("li", recursive=False):
            try:
                player_header = item.find("div", class_="date")
                if not player_header:
                    continue

                titulo = player_header.get_text(strip=True)
                parts = [p.strip() for p in re.split(r",|\n", titulo) if p.strip()]
                if len(parts) < 2:
                    logger.debug(f"Formato inesperado en título: '{titulo}'")
                    continue

                manager = parts[0]
                periodo = re.sub(r"(?i)^finaliza en\s*", "", parts[1])

                player_row = item.find("div", class_="player-row")
                if not player_row:
                    continue

                # Extraer subcomponentes
                jugador_div = player_row.find("div", class_="name")
                undername_div = player_row.find("div", class_="underName")
                pos_div = player_row.find("div", class_="player-position")
                points_div = player_row.find("div", class_="points")
                icons_div = player_row.find("div", class_="icons")
                avg_div = player_row.select_one("div.avg")

                # Nombre del jugador
                jugador = jugador_div.get_text(strip=True) if jugador_div else None

                # Estado (de SVG)
                estado = None
                if jugador_div:
                    svg = jugador_div.find("svg")
                    if svg:
                        use_tag = svg.find("use")
                        if use_tag and "href" in use_tag.attrs:
                            href = use_tag["href"]
                            if "#" in href:
                                estado = href.split("#")[-1].strip()

                # Precio
                precio = None
                if undername_div:
                    precio_text = undername_div.get_text(strip=True)
                    match = re.search(r"([\d\.,]+)", precio_text)
                    if match:
                        precio = match.group(1).replace(".", "").replace(",", ".")

                # Posición y puntos
                pos = pos_div.get("data-position") if pos_div else None
                points = points_div.get_text(strip=True) if points_div else None

                # Equipo (por logo)
                team = None
                if icons_div:
                    img_tag = icons_div.find("img", class_="team-logo")
                    if img_tag and "src" in img_tag.attrs:
                        match = re.search(r"/teams/(\d+)\.png", img_tag["src"])
                        if match:
                            team = match.group(1)

                # Puntos promedio
                avgpoints = avg_div.get_text(strip=True).replace(",", ".") if avg_div else None

                mercado.append({
                    "date": today,
                    "manager": manager,
                    "periodo": periodo,
                    "jugador": jugador,
                    "precio": float(precio) if precio else None,
                    "posicionJugador": int(pos) if pos else None,
                    "puntosJugador": int(points) if points else None,
                    "equipoLiga": team,
                    "avgPoints": float(avgpoints) if avgpoints else None,
                    "estado": estado
                })

            except Exception as inner_e:
                logger.debug(f"Error procesando jugador: {inner_e}")

        mercado['precio'] = mercado['precio'] / 1_000_000
        logger.info(f"✅ Extraídos {len(mercado)} jugadores del mercado.")
        return pd.DataFrame(mercado)

    except Exception as e:
        logger.exception(f"❌ Error general en extraer_mercado: {e}")
        return pd.DataFrame()
