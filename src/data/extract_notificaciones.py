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
        return _empty_notifications_df()

    # --- NUEVO: recorrer cada card-wrapper ---
    wrappers = feed.find_all("div", class_="card-wrapper", recursive=False)
    if not wrappers:
        logger.warning("No se encontraron 'card-wrapper' en el feed.")
        return _empty_notifications_df()

    for wrapper in wrappers:
        try:
            # ==========================
            #   INICIO DEL MERCADO
            # ==========================
            head_div = wrapper.find("div", class_="head")
            if head_div:
                title_div = head_div.find("div", class_="title")
                if title_div and title_div.get_text(strip=True) == "Nuevas transacciones en el mercado":
                    notificaciones.append({
                        "type": "marks",
                        "subtype": "start_mercado"
                    })
                    # seguimos, puede haber una card-transfer justo debajo
                    # no hacemos continue

            # ==========================
            #   TRANSFERENCIAS
            # ==========================
            transfer_card = wrapper.find("div", class_="card-transfer")
            if transfer_card:
                ul = transfer_card.find("ul", class_=["player-list", "player-list--secondary"])
                items = ul.find_all("li")
                if not items:
                    continue
                for item in items:    
                    title_div = item.find("div", class_="title")
                    price_div = item.find("div", class_="price")
                    team_div = item.find("div", class_="icons")
                    pos_div = item.find("div", class_="player-position")
                    points_div = item.find("div", class_="points")
                    if title_div and price_div:
                        jugador = _text_of(title_div.find("strong"))
                        equipos = title_div.find_all("em")
                        de_equipo = _text_of(equipos[0]) if len(equipos) > 0 else ""
                        a_equipo = _text_of(equipos[1]) if len(equipos) > 1 else ""

                        clausula = "cláusula" in title_div.get_text(strip=True, separator=" ").lower()
                        precio = price_div.get_text(strip=True)
                        pos = pos_div["data-position"] if (pos_div and pos_div.has_attr("data-position")) else ""
                        points = _text_of(points_div)

                        # ID de equipo
                        team = None
                        img_tag = team_div.find("img", class_="team-logo") if team_div else None
                        if img_tag and img_tag.has_attr("src"):
                            m = re.search(r"/teams/(\d+)\.png", img_tag["src"])
                            if m:
                                team = m.group(1)

                        # Subtipo de transferencia
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

                        # Pujas adicionales
                        other_bids_ul = item.find("ul", class_="other-bids")
                        if other_bids_ul:
                            li_bids = other_bids_ul.find_all("li")[1:]  # saltar título
                            for li in li_bids:
                                nombre_tag = li.find("strong")
                                nombre = _text_of(nombre_tag)
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

            # ==========================
            #   FIN DE JORNADA
            # ==========================
            gameweek_card = wrapper.find("div", class_="card-gameweek_end")
            if gameweek_card:
                ul = gameweek_card.find("ul", class_="player-list--secondary")
                if ul:
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

            # ==========================
            #   QUINIELA
            # ==========================
            quiniela_card = wrapper.find("div", class_="card-gameweek_end_pools")
            if quiniela_card:
                ul = quiniela_card.find("ul", class_="player-list--secondary")
                if ul:
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

            # ==========================
            #   INICIO DE JORNADA
            # ==========================
            start_jornada = wrapper.find("div", class_="card-gameweek_start")
            if start_jornada:
                title = start_jornada.find("h1", class_="title")
                if title:
                    m = re.search(r'Jornada\s+(\d+)', title.get_text())
                    if m:
                        numero_jornada = int(m.group(1))
                        notificaciones.append({
                            "type": "marks",
                            "subtype": "start_jornada",
                            "jornada": numero_jornada
                        })

        except Exception as e:
            logger.exception("Error procesando wrapper: %s", e)

    # --- construir el DataFrame final ---
    df = pd.DataFrame(notificaciones)
    today = pd.Timestamp.today().date()
    if not df.empty:
        df["date"] = today
    else:
        df = _empty_notifications_df()
        df["date"] = today

    all_columns = [
        "type","subtype","jugador","de_equipo","a_equipo","precio",
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
        "type","subtype","jugador","de_equipo","a_equipo","precio",
        "posicionJugador","puntosJugador","equipoLiga","name","money","position",
        "aciertos","points","jornada","date","idTransfer"
    ]
    return pd.DataFrame(columns=cols)
