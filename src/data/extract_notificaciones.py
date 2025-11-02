# src/data/extract_notificaciones.py
from bs4 import BeautifulSoup
import re
import pandas as pd
import hashlib
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

def generar_id_transfer(jugador: Optional[str], de_equipo: Optional[str], a_equipo: Optional[str], precio: Optional[str]) -> str:
    """
    Genera un identificador único (MD5 hex) para una transferencia/puja.
    """
    campos = [jugador or "", de_equipo or "", a_equipo or "", precio or ""]
    # Convertimos todo a texto, reemplazamos None por vacío
    concatenado = "|".join([str(c) if c is not None else "" for c in campos])
    return hashlib.md5(concatenado.encode('utf-8')).hexdigest()


def _text_of(tag):
    """Helper seguro para extraer texto o '' si tag es None."""
    return tag.get_text(strip=True) if tag else ""


def extraer_notificaciones(html: str) -> pd.DataFrame:
    """
    Extrae notificaciones desde el HTML proporcionado y devuelve un DataFrame.
    Tipos soportados: transfer, bonificacion (clasificacion/quiniela), marks (start_jornada/start_mercado).
    """
    soup = BeautifulSoup(html or "", "html.parser")
    notificaciones: List[Dict] = []

    feed = soup.find("div", class_="feed-cards")
    if not feed:
        logger.warning("No se encontró el contenedor principal 'feed-cards'. Devolviendo DataFrame vacío.")
        # devolver df con las columnas esperadas
        return _empty_notifications_df()

    # Recorremos nodos de primer nivel dentro del feed para reducir ruido
    for element in feed.find_all(recursive=False):
        classes = element.get("class", []) or []

        # --- Transferencias: li.item (estructura observada) ---
        try:
            if element.name == "li" and element.select_one(".item"):
                item = element.select_one(".item")
                title_div = item.find("div", class_="title")
                price_div = item.find("div", class_="price")
                team_div = item.find("div", class_="icons")
                pos_div = item.find("div", class_="player-position")
                points_div = item.find("div", class_="points")

                # seguridad: comprobar elementos básicos
                if title_div and price_div:
                    # jugador
                    strong = title_div.find("strong")
                    jugador = _text_of(strong)

                    # equipos (em)
                    equipos = title_div.find_all("em")
                    de_equipo = _text_of(equipos[0]) if len(equipos) > 0 else ""
                    a_equipo = _text_of(equipos[1]) if len(equipos) > 1 else ""

                    # clausula
                    clausula = "cláusula" in title_div.get_text(strip=True, separator=" ").lower()

                    # precio raw (podemos normalizar si hace falta)
                    precio = price_div.get_text(strip=True)

                    # posicion y puntos
                    pos = pos_div["data-position"] if (pos_div and pos_div.has_attr("data-position")) else ""
                    points = _text_of(points_div)

                    # equipo liga (extraer id del src si existe)
                    team = None
                    img_tag = None
                    if team_div:
                        img_tag = team_div.find("img", class_="team-logo")
                    if img_tag and img_tag.has_attr("src"):
                        src = img_tag["src"]
                        m = re.search(r"/teams/(\d+)\.png", src)
                        if m:
                            team = m.group(1)

                    # subtype
                    if clausula:
                        subtype = "clausula"
                    elif de_equipo == "Mister" or a_equipo == "Mister":
                        subtype = "mercado"
                    else:
                        subtype = "acuerdo"

                    id_transfer_principal = generar_id_transfer(jugador, de_equipo, a_equipo, precio)

                    notificaciones.append({
                        "type": "transfer",
                        "subtype": subtype,
                        "jugador": jugador,
                        "de_equipo": de_equipo,
                        "a_equipo": a_equipo,
                        "precio": precio,
                        "posicionJugador": pos,
                        "puntosJugador": points,
                        "equipoLiga": team,
                        "idTransfer": id_transfer_principal
                    })

                    # Otras pujas (lista de pujas), si existen
                    other_bids_ul = element.find("ul", class_="other-bids")
                    if other_bids_ul:
                        li_bids = other_bids_ul.find_all("li")[1:]  # saltar título
                        for li in li_bids:
                            nombre_tag = li.find("strong")
                            nombre = _text_of(nombre_tag) or None
                            texto = li.get_text(" ", strip=True)
                            partes = texto.split("›")
                            dinero = partes[-1].strip() if len(partes) > 1 else None

                            id_puja = generar_id_transfer(jugador, de_equipo, nombre, dinero)

                            notificaciones.append({
                                "type": "transfer",
                                "subtype": "Puja",
                                "jugador": jugador,
                                "de_equipo": de_equipo,
                                "a_equipo": nombre,
                                "precio": dinero,
                                "posicionJugador": pos,
                                "puntosJugador": points,
                                "equipoLiga": team,
                                "idTransfer": id_puja
                            })
                # fin if title_div and price_div
                continue  # pasar al siguiente element
        except Exception as e:
            logger.exception("Error procesando elemento transfer: %s", e)
            # continuar con el resto de elementos

        # --- Gameweek (resumen de jornada) ---
        try:
            if "card-gameweek_end" in classes:
                ul = element.find("ul", class_="player-list--secondary")
                if not ul:
                    continue
                for li in ul.find_all("li", recursive=False):
                    player_row = li.find("div", class_="player-row")
                    if not player_row:
                        continue
                    name = player_row.find("div", class_="name")
                    money = player_row.find("div", class_="green")
                    position = player_row.find("div", class_="position")
                    points = player_row.select_one("div.points > div.value")

                    notificaciones.append({
                        "type": "bonificacion",
                        "subtype": "clasificacion",
                        "name": _text_of(name),
                        "money": _text_of(money).replace("+", ""),
                        "position": _text_of(position),
                        "points": _text_of(points)
                    })
                continue
        except Exception as e:
            logger.exception("Error procesando card-gameweek_end: %s", e)

        # --- Quiniela ---
        try:
            if "card-gameweek_end_pools" in classes:
                ul = element.find("ul", class_="player-list--secondary")
                if not ul:
                    continue
                for li in ul.find_all("li", recursive=False):
                    player_row = li.find("div", class_="player-row")
                    if not player_row:
                        continue
                    name = player_row.find("div", class_="name")
                    money = player_row.find("div", class_="green")
                    position = player_row.find("div", class_="position")
                    aciertos = player_row.select_one("div.points > div.value")

                    notificaciones.append({
                        "type": "bonificacion",
                        "subtype": "quiniela",
                        "name": _text_of(name),
                        "money": _text_of(money),
                        "position": _text_of(position),
                        "aciertos": _text_of(aciertos)
                    })
                continue
        except Exception as e:
            logger.exception("Error procesando card-gameweek_end_pools: %s", e)

        # --- Inicio de jornada ---
        try:
            if "card-gameweek_start" in classes:
                title = element.find("h1", class_="title")
                if title:
                    m = re.search(r'Jornada\s+(\d+)', title.get_text())
                    if m:
                        numero_jornada = int(m.group(1))
                        notificaciones.append({
                            "type": "marks",
                            "subtype": "start_jornada",
                            "jornada": numero_jornada
                        })
                continue
        except Exception as e:
            logger.exception("Error procesando card-gameweek_start: %s", e)

        # --- Inicio del mercado ---
        try:
            # Detección por div.left y texto título
            if element.name == "div" and "left" in classes:
                title_div = element.find("div", class_="title")
                if title_div and title_div.get_text(strip=True) == "Nuevas transacciones en el mercado":
                    notificaciones.append({
                        "type": "marks",
                        "subtype": "start_mercado",
                        "mensaje": "Nuevas transacciones en el mercado"
                    })
                continue
        except Exception as e:
            logger.exception("Error procesando inicio de mercado: %s", e)

    # Final: construir DataFrame con columnas estables
    df = pd.DataFrame(notificaciones)
    today = pd.Timestamp.today().date()
    if not df.empty:
        df['date'] = today
    else:
        # crear DF vacío con columnas obligatorias
        df = _empty_notifications_df()
        df['date'] = today

    # Asegurar columnas
    all_columns = [
        "type","subtype","mensaje","jugador","de_equipo","a_equipo","precio",
        "posicionJugador","puntosJugador","equipoLiga","name","money","position",
        "aciertos","points","jornada","date","idTransfer"
    ]
    for col in all_columns:
        if col not in df.columns:
            df[col] = None

    df = df[all_columns]
    return df


def _empty_notifications_df() -> pd.DataFrame:
    """Devuelve un DataFrame vacío con las columnas esperadas."""
    cols = [
        "type","subtype","mensaje","jugador","de_equipo","a_equipo","precio",
        "posicionJugador","puntosJugador","equipoLiga","name","money","position",
        "aciertos","points","jornada","date","idTransfer"
    ]
    return pd.DataFrame(columns=cols)
