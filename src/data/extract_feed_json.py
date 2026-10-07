"""
Notificaciones del feed a partir del JSON de /ajax/feed.

Produce exactamente las mismas filas, en el mismo orden y con el mismo
`idTransfer` que extraer_notificaciones() sobre el HTML, para que el merge
(merge_feed_cards_until_match) y el preprocesado (que numera los días de
mercado según la posición de los marcadores start_mercado) no cambien.

Diferencias respecto al HTML, todas a mejor:
  - `date` es el día real de la tarjeta (`created`), no el día del scrape.
  - `created` guarda fecha y hora exactas.
  - `aciertos` (quiniela) y `points` (fin de jornada) vienen rellenos; el
    HTML los dejaba vacíos.
  - No depende de clases CSS que pueden cambiar con un rediseño.
"""
import logging

import pandas as pd

from src.data.extract_notificaciones import _empty_notifications_df, generar_id_transfer

logger = logging.getLogger(__name__)

COLUMNS = list(_empty_notifications_df().columns) + ["created"]


def _miles(n) -> str | None:
    """17105210 -> '17.105.210', como lo muestra la web (y como entra en el hash)."""
    if n is None:
        return None
    return f"{int(n):,}".replace(",", ".")


def _millones(n):
    return int(n) / 1_000_000 if n is not None else None


def _str(v):
    return None if v is None else str(v)


def _transfer_rows(item: dict) -> list[dict]:
    jugador, de_equipo, a_equipo = item.get("name"), item.get("from"), item.get("to")
    precio_txt = _miles(item.get("price"))
    if item.get("type") == "clause":
        subtype = "clausula"
    elif de_equipo == "Mister" or a_equipo == "Mister":
        subtype = "mercado"
    else:
        subtype = "acuerdo"

    comunes = {
        "type": "transfer",
        "jugador": jugador,
        "de_equipo": de_equipo,
        "posicionJugador": _str(item.get("position")),
        "puntosJugador": _str(item.get("points")),
        "equipoLiga": _str(item.get("id_team")),
    }
    filas = [{**comunes, "subtype": subtype, "a_equipo": a_equipo, "precio": _millones(item.get("price")),
              "idTransfer": generar_id_transfer(jugador, de_equipo, a_equipo, precio_txt)}]
    for bid in item.get("other_bids") or []:
        filas.append({**comunes, "subtype": "Puja", "a_equipo": bid.get("name"),
                      "precio": _millones(bid.get("bid")),
                      "idTransfer": generar_id_transfer(jugador, de_equipo, bid.get("name"), _miles(bid.get("bid")))})
    return filas


def _card_rows(card: dict) -> list[dict]:
    cat, data = card.get("category"), card.get("data")
    if cat == "transfer":
        filas = [{"type": "marks", "subtype": "start_mercado"}]
        for item in data or []:
            filas += _transfer_rows(item)
        return filas
    if cat == "gameweek_end":
        posiciones = (((data or {}).get("ranking") or {}).get("ranking") or {}).get("positions") or []
        return [{
            "type": "bonificacion", "subtype": "clasificacion",
            "name": (p.get("user") or {}).get("name"),
            "money": _millones(p.get("payment")),
            "position": _str(p.get("rank")),
            "points": _str(p.get("points")),
        } for p in posiciones]
    if cat == "gameweek_end_pools":
        return [{
            "type": "bonificacion", "subtype": "quiniela",
            "name": p.get("name"),
            "money": _millones(p.get("amount")),
            "position": f"{i}º",
            "aciertos": _str(p.get("hits")),
        } for i, p in enumerate((data or {}).get("table") or [], start=1)]
    if cat == "gameweek_start" and (data or {}).get("gameweek") is not None:
        return [{"type": "marks", "subtype": "start_jornada", "jornada": int(data["gameweek"])}]
    return []  # post, porra, blog, pool_public, clauses_drops: el HTML tampoco los guardaba


def extraer_feed_json(cards: list[dict]) -> pd.DataFrame:
    """`cards`: tarjetas del feed en orden (más reciente primero), tal como
    llegan en data[] de /ajax/feed concatenando las páginas."""
    filas = []
    for card in cards or []:
        try:
            created = card.get("created")
            for fila in _card_rows(card):
                fila["created"] = created
                fila["date"] = created[:10] if created else None
                filas.append(fila)
        except Exception as e:
            logger.warning("Tarjeta del feed ignorada (%s): %s", e, card.get("id"))
    df = pd.DataFrame(filas)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[COLUMNS]


def cards_de_respuestas(respuestas: list[dict]) -> list[dict]:
    """Concatena las tarjetas de varias respuestas de /ajax/feed ordenadas por
    offset y sin repetir (por id de tarjeta)."""
    vistas, cards = set(), []
    for r in sorted(respuestas, key=lambda r: r.get("offset", 0)):
        data = (r.get("body") or {}).get("data")
        for c in data if isinstance(data, list) else []:
            if c.get("id") not in vistas:
                vistas.add(c.get("id"))
                cards.append(c)
    return cards
