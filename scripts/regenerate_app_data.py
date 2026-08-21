"""
regenerate_app_data.py
======================
Regenera web/data/app-data.json a partir de los CSVs procesados y los
JSONs de periódico ya generados.

Uso:
    python scripts/regenerate_app_data.py

No necesita tokens de IA ni conexión a internet.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ── Entorno ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.utils.config_loader import load_config
from src.utils.file_utils import safe_read_csv
from src.utils.team_map import map_team


class _NumpyEncoder(json.JSONEncoder):
    """Convierte tipos numpy/pandas a tipos nativos de Python."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
cfg = load_config(validate_env=False)

CSV_GAMEWEEK      = cfg["paths"]["csv"]["gameweek"]
CSV_CLASIFICACION = cfg["paths"]["csv"]["clasificaciones"]
CSV_QUINIELAS     = cfg["paths"]["csv"]["quiniela"]
CSV_MERCADO       = cfg["paths"]["csv"]["notificaciones_clean"]
CSV_JUGADORES     = cfg["paths"]["csv"]["jugadores"]
NEWS_JSON_DIR     = ROOT / "newspaper" / "json"
OUTPUT_PATH       = ROOT / "web" / "data" / "app-data.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

LEAGUE_NAME   = "Sotano League"
SEASON        = cfg["season"]["current"]
N_FORM_ROUNDS = 8   # últimas N jornadas para calcular el form


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_csv(path: str, name: str) -> pd.DataFrame:
    """Lee `name` (CSV en disco o tabla de BD según config.yaml) vía
    safe_read_csv, que resuelve la temporada activa automáticamente."""
    df = safe_read_csv(path)
    if df.empty:
        logger.error("Sin datos para %s (%s)", name, path)
        sys.exit(1)
    logger.info("  %s: %d filas", name, len(df))
    return df


def _safe_str(val) -> str:
    """Convierte NaN / None a cadena vacía."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    return str(val)


# ─────────────────────────────────────────────────────────────────────────────
# Sección: playersMap
# ─────────────────────────────────────────────────────────────────────────────

def build_players_map(df_jugadores: pd.DataFrame) -> dict:
    """{ nombre_jugador: url_foto }"""
    result = {}
    for _, row in df_jugadores.iterrows():
        nombre = _safe_str(row.get("nombre"))
        foto   = _safe_str(row.get("foto_url"))
        if nombre and foto:
            result[nombre] = foto
    logger.info("playersMap: %d jugadores", len(result))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Sección: clasificación general y quinielas
# ─────────────────────────────────────────────────────────────────────────────

def build_standings(df_clas: pd.DataFrame) -> list:
    """Clasificación general acumulada."""
    total = (
        df_clas.groupby("nombre")["puntos"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    return [
        {"rank": i + 1, "manager": row["nombre"], "points": int(row["puntos"])}
        for i, row in total.iterrows()
    ]


def build_pool_standings(df_quin: pd.DataFrame) -> list:
    """Clasificación de quinielas acumulada."""
    total = (
        df_quin.groupby("nombre")["puntos"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    return [
        {"rank": i + 1, "manager": row["nombre"], "points": int(row["puntos"])}
        for i, row in total.iterrows()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Sección: stats por manager
# ─────────────────────────────────────────────────────────────────────────────

def build_managers(
    df_gw: pd.DataFrame,
    df_clas: pd.DataFrame,
    df_transfers: pd.DataFrame,
    standings: list,
) -> list:
    managers = []

    # Clasificación general para posición y total
    total_points = {s["manager"]: s["points"] for s in standings}
    position_map = {s["manager"]: s["rank"] for s in standings}

    # Última jornada para weekPoints
    last_jornada = int(df_gw["Jornada"].max())

    # Jornadas para form (últimas N)
    all_jornadas = sorted(df_gw["Jornada"].unique())
    form_jornadas = all_jornadas[-N_FORM_ROUNDS:]

    for manager in sorted(total_points.keys()):
        df_m = df_gw[df_gw["Manager"] == manager]
        df_t = df_transfers[df_transfers["equipo"] == manager]

        # Puntos por jornada
        pts_jornada = df_m.groupby("Jornada")["Puntos"].sum()

        # week points
        week_points = int(pts_jornada.get(last_jornada, 0))

        # stats generales
        avg   = round(float(pts_jornada.mean()), 2) if len(pts_jornada) else 0.0
        std   = round(float(pts_jornada.std()),  2) if len(pts_jornada) > 1 else 0.0
        goals = int(df_m["Goles"].sum())
        assis = int(df_m["Asistencias"].sum())
        reds  = int(df_m["Roja"].sum())

        # mejor y peor jugador (total temporada)
        pts_jugador = df_m.groupby(["NombreJugador", "EquipoJugador", "Posicion"])["Puntos"].sum()
        best_player = worst_player = best_historic = None
        if not pts_jugador.empty:
            # histórico absoluto
            best_idx = pts_jugador.idxmax()
            best_historic = {
                "name":     best_idx[0],
                "team":     map_team(best_idx[1]),
                "position": best_idx[2],
                "points":   int(pts_jugador[best_idx]),
            }
            # mejor esta temporada (mismo que historic, pero lo dejamos igual)
            best_player = best_historic.copy()

            worst_idx = pts_jugador.idxmin()
            worst_player = {
                "name":     worst_idx[0],
                "team":     map_team(worst_idx[1]),
                "position": worst_idx[2],
                "points":   int(pts_jugador[worst_idx]),
            }

        # mercado
        compras  = df_t[df_t["compra-venta"] == "compra"]
        clausulas = compras[compras["subtype"] == "clausula"]
        acuerdos  = compras[compras["subtype"] == "acuerdo"]
        mercado_c = compras[compras["subtype"] == "mercado"]

        market_spend = round(float(compras["ganancias"].abs().sum()), 2)

        # form: puntos de las últimas N jornadas
        form = [int(pts_jornada.get(j, 0)) for j in form_jornadas]

        managers.append({
            "name":             manager,
            "position":         position_map.get(manager, 0),
            "totalPoints":      total_points.get(manager, 0),
            "weekPoints":       week_points,
            "average":          avg,
            "stdDev":           std,
            "goals":            goals,
            "assists":          assis,
            "redCards":         reds,
            "bestPlayer":       best_player,
            "worstPlayer":      worst_player,
            "bestPlayerHistoric": best_historic,
            "transferCount":    len(compras),
            "marketSpend":      market_spend,
            "market": {
                "mercado":   len(mercado_c),
                "clausulas": len(clausulas),
                "acuerdos":  len(acuerdos),
            },
            "form":       form,
            "comparison": {},
        })

    logger.info("Managers procesados: %d", len(managers))
    return managers


# ─────────────────────────────────────────────────────────────────────────────
# Sección: league-level stats
# ─────────────────────────────────────────────────────────────────────────────

def build_league(
    df_gw: pd.DataFrame,
    df_clas: pd.DataFrame,
    df_transfers: pd.DataFrame,
    standings: list,
    pool_standings: list,
    news_cards: list,
) -> dict:

    # Rango de fechas
    dates = pd.to_datetime(df_gw["Date"])
    date_range = f"{dates.min().date()} · {dates.max().date()}"

    # Manager del mes (última jornada disponible)
    last_jornada = int(df_gw["Jornada"].max())
    df_last = df_gw[df_gw["Jornada"] == last_jornada]
    pts_last = df_last.groupby("Manager")["Puntos"].sum()
    manager_of_month = None
    if not pts_last.empty:
        best_mgr = pts_last.idxmax()
        manager_of_month = {
            "name":        best_mgr,
            "subtitle":    "Manager en mejor forma",
            "description": f"{best_mgr} lideró la última jornada con {int(pts_last[best_mgr])} puntos.",
        }

    # Jugador del mes (mayor puntuación individual en la última jornada)
    player_of_month = None
    if not df_last.empty:
        idx = df_last["Puntos"].idxmax()
        row = df_last.loc[idx]
        player_of_month = {
            "name":        row["NombreJugador"],
            "team":        str(row["EquipoJugador"]),
            "manager":     row["Manager"],
            "points":      int(row["Puntos"]),
            "description": f"{row['NombreJugador']} firmó {int(row['Puntos'])} puntos.",
        }

    # Titular más reciente del periódico
    latest_headline = news_cards[0] if news_cards else None

    # Mercado: compras por tipo
    compras = df_transfers[df_transfers["compra-venta"] == "compra"].copy()
    compras["ganancias_abs"] = compras["ganancias"].abs()

    mercado   = compras[compras["subtype"] == "mercado"]
    clausulas = compras[compras["subtype"] == "clausula"]

    most_expensive_buy = None
    if not mercado.empty:
        idx = mercado["ganancias_abs"].idxmax()
        r = mercado.loc[idx]
        most_expensive_buy = {
            "player":  _safe_str(r["jugador"]),
            "manager": _safe_str(r["equipo"]),
            "amount":  round(float(r["ganancias_abs"]), 2),
        }

    most_expensive_clause = None
    if not clausulas.empty:
        idx = clausulas["ganancias_abs"].idxmax()
        r = clausulas.loc[idx]
        most_expensive_clause = {
            "player":  _safe_str(r["jugador"]),
            "manager": _safe_str(r["equipo"]),
            "amount":  round(float(r["ganancias_abs"]), 2),
        }

    # Managers que más clausulazos han dado / recibido
    # "dado" = haber vendido por cláusula (la víctima)
    ventas_clausula = df_transfers[
        (df_transfers["compra-venta"] == "venta") &
        (df_transfers["subtype"] == "clausula")
    ]
    most_clauses_given = None
    if not ventas_clausula.empty:
        top = ventas_clausula["equipo"].value_counts().idxmax()
        most_clauses_given = {
            "manager": top,
            "count":   int(ventas_clausula["equipo"].value_counts()[top]),
        }

    most_clauses_received = None
    if not clausulas.empty:
        top = clausulas["equipo"].value_counts().idxmax()
        most_clauses_received = {
            "manager": top,
            "count":   int(clausulas["equipo"].value_counts()[top]),
        }

    # Top 5 clausulazos y transferencias de mercado
    top_clauses = []
    if not clausulas.empty:
        for _, r in clausulas.nlargest(5, "ganancias_abs").iterrows():
            # Para saber el vendedor buscamos la venta del mismo jugador misma fecha
            venta = ventas_clausula[
                (ventas_clausula["jugador"] == r["jugador"]) &
                (ventas_clausula["fecha"] == r["fecha"])
            ]
            from_mgr = venta["equipo"].iloc[0] if not venta.empty else "?"
            top_clauses.append({
                "player": _safe_str(r["jugador"]),
                "from":   from_mgr,
                "to":     _safe_str(r["equipo"]),
                "amount": round(float(r["ganancias_abs"]), 2),
            })

    top_transfers = []
    if not mercado.empty:
        for _, r in mercado.nlargest(5, "ganancias_abs").iterrows():
            top_transfers.append({
                "player":  _safe_str(r["jugador"]),
                "manager": _safe_str(r["equipo"]),
                "amount":  round(float(r["ganancias_abs"]), 2),
            })

    return {
        "name":                 LEAGUE_NAME,
        "season":               SEASON,
        "dateRange":            date_range,
        "standings":            standings,
        "poolStandings":        pool_standings,
        "managerOfMonth":       manager_of_month,
        "playerOfMonth":        player_of_month,
        "latestHeadline":       latest_headline,
        "mostExpensiveBuy":     most_expensive_buy,
        "mostExpensiveClause":  most_expensive_clause,
        "mostClausesGiven":     most_clauses_given,
        "mostClausesReceived":  most_clauses_received,
        "topClauses":           top_clauses,
        "topTransfers":         top_transfers,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sección: news (periódicos generados)
# ─────────────────────────────────────────────────────────────────────────────

def build_news(news_json_dir: Path) -> list:
    """
    Lee todos los jornada_XX_cards.json desde cards/ y articles/
    y construye la lista de noticias para la web app.
    """
    news = []
    articles_dir = news_json_dir / "articles"
    cards_dir = news_json_dir / "cards"

    json_files = sorted(articles_dir.glob("jornada_*_json.json"), reverse=True)

    for jf in json_files:
        jornada_stem = jf.stem.replace("_json", "")  # jornada_18
        jornada_label = jornada_stem.replace("jornada_", "J")  # J18

        cards_file = cards_dir / f"{jornada_stem}_cards.json"
        if not cards_file.exists():
            continue

        try:
            cards_data = json.loads(cards_file.read_text(encoding="utf-8"))
            cards = cards_data.get("cards", [])
            if not cards:
                continue

            # Card de clasificacion como portada; fallback al primero
            portada = next((c for c in cards if c.get("tipo") == "clasificacion"), cards[0])

            # Convertir al formato esperado por la web
            web_cards = [
                {
                    "type":     c.get("tipo", ""),
                    "title":    c.get("titulo", ""),
                    "subtitle": c.get("subtitulo", ""),
                    "text":     c.get("texto", []),
                    "jugador":  c.get("jugador"),
                    "manager":  c.get("manager"),
                    "puntos":   c.get("puntos"),
                    "dinero":   c.get("dinero"),
                }
                for c in cards
            ]

            news.append({
                "date":            jornada_label,
                "title":           portada.get("titulo", ""),
                "subtitle":        portada.get("subtitulo", ""),
                "summary":         " ".join(portada.get("texto", [])),
                "cards":           web_cards,
                "standingsAtIssue": _load_standings_snapshot(jf),
            })
        except Exception as e:
            logger.warning("Error leyendo %s: %s", cards_file.name, e)

    logger.info("News cargadas: %d periodicos", len(news))
    return news


def _load_standings_snapshot(articles_file: Path) -> list:
    """
    Extrae clasificacion.general del articles/jornada_N_json.json de esa
    edición, para poder mostrar cómo estaba la tabla en ese momento (no solo
    la clasificación acumulada actual).
    """
    try:
        events_data = json.loads(articles_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("No se pudo leer clasificación histórica de %s: %s", articles_file.name, e)
        return []

    general = (events_data.get("clasificacion") or {}).get("general") or {}
    rows = [
        {"rank": stats.get("posicion"), "manager": manager, "points": stats.get("puntos")}
        for manager, stats in general.items()
    ]
    rows.sort(key=lambda row: row["rank"] if row["rank"] is not None else 999)
    return rows


def _get_latest_headline(news: list) -> dict | None:
    """Devuelve la primera card del periódico más reciente."""
    if not news:
        return None
    return news[0]["cards"][0] if news[0].get("cards") else None


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    logger.info("Cargando CSVs...")
    df_gw   = _load_csv(CSV_GAMEWEEK,      "gameweek")
    df_clas = _load_csv(CSV_CLASIFICACION, "clasificaciones")
    df_quin = _load_csv(CSV_QUINIELAS,     "quinielas")
    df_merc = _load_csv(CSV_MERCADO,       "mercado/notificaciones")
    df_jug  = _load_csv(CSV_JUGADORES,     "jugadores")

    # Solo transfers
    df_transfers = df_merc[df_merc["type"] == "transfer"].copy()

    logger.info("Construyendo secciones...")

    players_map  = build_players_map(df_jug)
    standings    = build_standings(df_clas)
    pool_stand   = build_pool_standings(df_quin)
    managers     = build_managers(df_gw, df_clas, df_transfers, standings)
    news         = build_news(NEWS_JSON_DIR)
    latest_card  = _get_latest_headline(news)
    league       = build_league(df_gw, df_clas, df_transfers, standings, pool_stand, [latest_card] if latest_card else [])

    app_data = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "league":      league,
        "managers":    managers,
        "news":        news,
        "playersMap":  players_map,
    }

    OUTPUT_PATH.write_text(
        json.dumps(app_data, ensure_ascii=False, indent=2, cls=_NumpyEncoder),
        encoding="utf-8",
    )
    logger.info("app-data.json generado -> %s", OUTPUT_PATH)
    logger.info(
        "  %d managers | %d noticias | %d jugadores en mapa",
        len(managers), len(news), len(players_map),
    )


if __name__ == "__main__":
    main()
