"""
run_web_data.py — Genera web/data/app-data.json desde los CSVs del proyecto.

Ejecutar:
    python scripts/run_web_data.py

Lógica de cálculo:
- Clasificación general/porra: toda la temporada
- Manager del mes / Jugador del mes: jornadas "En juego" del mes anterior
- KPIs de la liga: toda la temporada
- Movimientos del mes (top clausulazos/fichajes): últimos 30 días
- Datos por manager: toda la temporada
"""

import os
import sys
import json
import math
import logging
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

# ── Ajuste de rutas ──────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from src.utils.config_loader import load_config
from src.utils.file_utils import safe_read_csv, safe_read_json
from src.AI_newspaper.generate_json import TEAM_MAP, TEAM_POSICION

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

cfg = load_config()
csv = cfg["paths"]["csv"]
json_news_dir = cfg["paths"]["json"]["news"]
OUTPUT_PATH = ROOT_DIR / "web" / "data" / "app-data.json"


# ── Helpers ──────────────────────────────────────────────────────────────────

def safe_val(val):
    """Convierte NaN/inf a None para JSON."""
    if val is None:
        return None
    try:
        if math.isnan(val) or math.isinf(val):
            return None
    except TypeError:
        pass
    return val


def round2(val):
    v = safe_val(val)
    return round(float(v), 2) if v is not None else None


def last_30_days_mask(series: pd.Series) -> pd.Series:
    """Máscara para filas de los últimos 30 días."""
    cutoff = pd.Timestamp.today() - timedelta(days=30)
    return pd.to_datetime(series) >= cutoff


def prev_month_jornadas(df_jornadas: pd.DataFrame) -> list:
    """
    Devuelve los números de jornada que estuvieron 'En juego'
    durante el mes anterior al actual.
    """
    df = df_jornadas.copy()
    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp.today()
    first_this_month = today.replace(day=1)
    prev_month = (first_this_month - pd.Timedelta(days=1)).to_period("M")
    mask = (df["date"].dt.to_period("M") == prev_month) & (df["detalles"] == "En juego")
    return df.loc[mask, "jornada"].unique().tolist()


# ── Carga de CSVs ────────────────────────────────────────────────────────────

logger.info("Cargando CSVs...")

df_clas = safe_read_csv(csv["clasificaciones"])
df_clean = safe_read_csv(csv["notificaciones_clean"])
df_clausulas = safe_read_csv(csv["clausulas_acuerdos"])
df_gameweek = safe_read_csv(csv["gameweek"])
df_jornadas = safe_read_csv(csv["jornada"])
df_diff = safe_read_csv(csv["notificaciones_jugador"])

for name, df in [("clasificaciones", df_clas), ("ganancias_clean", df_clean),
                 ("clausulas_acuerdos", df_clausulas), ("gameweek", df_gameweek),
                 ("jornadas", df_jornadas)]:
    if df is None:
        logger.error(f"No se pudo cargar {name}.csv")
        sys.exit(1)

# Normalizar fechas
df_clean["fecha"] = pd.to_datetime(df_clean["fecha"])
df_clausulas["date"] = pd.to_datetime(df_clausulas["date"])
df_gameweek["Date"] = pd.to_datetime(df_gameweek["Date"])
df_jornadas["date"] = pd.to_datetime(df_jornadas["date"])
if df_diff is not None:
    df_diff["fecha"] = pd.to_datetime(df_diff["fecha"])

managers = sorted(df_clas["nombre"].dropna().unique().tolist())


# ── 1. Clasificación general ─────────────────────────────────────────────────

logger.info("Calculando clasificación general...")

standings_df = (
    df_clas.groupby("nombre", as_index=False)["puntos"]
    .sum()
    .sort_values("puntos", ascending=False)
    .reset_index(drop=True)
)
standings_df["rank"] = standings_df.index + 1
standings = [
    {"rank": int(r["rank"]), "manager": r["nombre"], "points": int(r["puntos"])}
    for _, r in standings_df.iterrows()
]


# ── 2. Clasificación de porra ────────────────────────────────────────────────

df_quiniela = safe_read_csv(csv["quiniela"])
if df_quiniela is not None:
    pool_df = (
        df_quiniela.groupby("nombre", as_index=False)["puntos"]
        .sum()
        .sort_values("puntos", ascending=False)
        .reset_index(drop=True)
    )
    pool_df["rank"] = pool_df.index + 1
    pool_standings = [
        {"rank": int(r["rank"]), "manager": r["nombre"], "points": int(r["puntos"])}
        for _, r in pool_df.iterrows()
    ]
else:
    pool_standings = []


# ── 3. Manager del mes y Jugador del mes ─────────────────────────────────────
# Usa jornadas "En juego" del mes anterior (igual que monthly_dashboard.py)

logger.info("Calculando manager y jugador del mes...")

jornadas_mes = prev_month_jornadas(df_jornadas)

if jornadas_mes:
    clas_mes = df_clas[df_clas["jornada"].isin(jornadas_mes)]
    clas_mensual = (
        clas_mes.groupby("nombre", as_index=False)["puntos"]
        .sum()
        .sort_values("puntos", ascending=False)
        .reset_index(drop=True)
    )
    if not clas_mensual.empty:
        top = clas_mensual.iloc[0]
        manager_of_month = {
            "name": top["nombre"],
            "subtitle": "Manager en mejor forma",
            "description": f"{top['nombre']} lideró el mes con {int(top['puntos'])} puntos.",
            "points": int(top["puntos"]),
        }
    else:
        manager_of_month = {"name": "Sin datos", "subtitle": "Pendiente", "description": "", "points": 0}

    # Jugador del mes: mayor puntos en una sola jornada del mes
    gw_mes = df_gameweek[df_gameweek["Jornada"].isin(jornadas_mes)]
    if not gw_mes.empty:
        best_row = gw_mes.loc[gw_mes["Puntos"].idxmax()]
        player_of_month = {
            "name": best_row["NombreJugador"],
            "team": str(best_row["EquipoJugador"]),
            "manager": best_row["Manager"],
            "points": int(best_row["Puntos"]),
            "description": f"{best_row['NombreJugador']} firmó {int(best_row['Puntos'])} puntos.",
        }
    else:
        player_of_month = {"name": "Sin datos", "description": "Sin jugador destacado."}
else:
    logger.warning("No hay jornadas del mes anterior — usando datos de la última jornada disponible")
    last_jornada = df_clas["jornada"].max()
    clas_mes = df_clas[df_clas["jornada"] == last_jornada]
    top = clas_mes.sort_values("puntos", ascending=False).iloc[0]
    manager_of_month = {
        "name": top["nombre"],
        "subtitle": "Mejor última jornada",
        "description": f"{top['nombre']} lideró con {int(top['puntos'])} puntos.",
        "points": int(top["puntos"]),
    }
    gw_last = df_gameweek[df_gameweek["Jornada"] == last_jornada]
    if not gw_last.empty:
        best_row = gw_last.loc[gw_last["Puntos"].idxmax()]
        player_of_month = {
            "name": best_row["NombreJugador"],
            "team": str(best_row["EquipoJugador"]),
            "manager": best_row["Manager"],
            "points": int(best_row["Puntos"]),
            "description": f"{best_row['NombreJugador']} firmó {int(best_row['Puntos'])} puntos.",
        }
    else:
        player_of_month = {"name": "Sin datos", "description": "Sin jugador destacado."}


# ── 4. KPIs de la liga — TODA LA TEMPORADA ───────────────────────────────────

logger.info("Calculando KPIs de toda la temporada...")

# Fichaje de mercado más caro (toda la temporada)
df_compras = df_clean[
    (df_clean["type"] == "transfer") &
    (df_clean["subtype"] == "mercado") &
    (df_clean["compra-venta"] == "compra")
]
if not df_compras.empty:
    row = df_compras.loc[df_compras["ganancias"].abs().idxmax()]
    most_expensive_buy = {
        "player": row["jugador"],
        "manager": row["equipo"],
        "amount": round2(abs(row["ganancias"])),
    }
else:
    most_expensive_buy = None

# Clausulazo más caro (toda la temporada)
df_claus_all = df_clausulas[df_clausulas["subtype"] == "clausula"]
if not df_claus_all.empty:
    row = df_claus_all.loc[df_claus_all["precio"].idxmax()]
    most_expensive_clause = {
        "player": row["jugador"],
        "manager": row["a_equipo"],
        "amount": round2(row["precio"]),
    }
    given_counts = df_claus_all.groupby("a_equipo")["precio"].count()
    most_clauses_given = {
        "manager": given_counts.idxmax(),
        "count": int(given_counts.max()),
    }
    received_counts = df_claus_all.groupby("de_equipo")["precio"].count()
    most_clauses_received = {
        "manager": received_counts.idxmax(),
        "count": int(received_counts.max()),
    }
else:
    most_expensive_clause = None
    most_clauses_given = None
    most_clauses_received = None


# ── 5. Movimientos del mes — últimos 30 días ─────────────────────────────────

logger.info("Calculando movimientos de los últimos 30 días...")

df_claus_30 = df_clausulas[
    last_30_days_mask(df_clausulas["date"]) & (df_clausulas["subtype"] == "clausula")
]
top_clauses = [
    {
        "player": r["jugador"],
        "from": r["de_equipo"],
        "to": r["a_equipo"],
        "amount": round2(r["precio"]),
    }
    for _, r in df_claus_30.sort_values("precio", ascending=False).head(3).iterrows()
]

df_compras_30 = df_clean[
    last_30_days_mask(df_clean["fecha"]) &
    (df_clean["type"] == "transfer") &
    (df_clean["subtype"] == "mercado") &
    (df_clean["compra-venta"] == "compra")
]
top_transfers = [
    {
        "player": r["jugador"],
        "manager": r["equipo"],
        "amount": round2(abs(r["ganancias"])),
    }
    for _, r in df_compras_30.sort_values("ganancias").head(3).iterrows()
]


# ── 6. Titular de la última noticia ──────────────────────────────────────────

latest_headline = {}
news_path = ROOT_DIR / json_news_dir / "news_cards.json"
if news_path.exists():
    cards_data = safe_read_json(str(news_path))
    if cards_data and "cards" in cards_data:
        for card in cards_data["cards"]:
            if card.get("tipo") == "clasificacion":
                latest_headline = card
                break


# ── 7. Datos por manager ─────────────────────────────────────────────────────

logger.info("Calculando datos por manager...")

managers_data = []

for manager in managers:
    # Puntos totales y posición
    total_pts = int(standings_df.loc[standings_df["nombre"] == manager, "puntos"].sum())
    pos_vals = standings_df.loc[standings_df["nombre"] == manager, "rank"].values
    position = int(pos_vals[0]) if len(pos_vals) > 0 else None

    # Puntos por jornada
    pts_jornada = (
        df_clas[df_clas["nombre"] == manager]
        .groupby("jornada")["puntos"]
        .sum()
        .sort_index()
    )
    avg = round2(pts_jornada.mean()) if not pts_jornada.empty else 0
    std = round2(pts_jornada.std()) if len(pts_jornada) > 1 else 0
    form = [int(v) for v in pts_jornada.tail(8).tolist()]
    week_pts = int(pts_jornada.iloc[-1]) if not pts_jornada.empty else 0

    # Gameweek stats
    gw_manager = df_gameweek[df_gameweek["Manager"] == manager]
    goals = int(gw_manager["Goles"].sum())
    assists = int(gw_manager["Asistencias"].sum())
    red_cards = int(gw_manager["Roja"].sum())

    def player_dict(row, points_override=None):
        return {
            "name": row["NombreJugador"],
            "team": TEAM_MAP.get(row["EquipoJugador"], str(row["EquipoJugador"])),
            "position": TEAM_POSICION.get(row["Posicion"], str(row["Posicion"])),
            "points": points_override if points_override is not None else int(row["Puntos"]),
        }

    last_jornada = df_gameweek["Jornada"].max()
    gw_last = gw_manager[gw_manager["Jornada"] == last_jornada]

    # Mejor jugador histórico — suma total de puntos por jugador en toda la temporada
    if not gw_manager.empty:
        pts_by_player = gw_manager.groupby("NombreJugador")["Puntos"].sum()
        best_hist_name = pts_by_player.idxmax()
        best_hist_pts = int(pts_by_player.max())
        best_hist_row = gw_manager[gw_manager["NombreJugador"] == best_hist_name].iloc[0]
        best_player_historic = player_dict(best_hist_row, points_override=best_hist_pts)
    else:
        best_player_historic = {"name": "Sin datos", "team": None, "position": None, "points": 0}

    # Jugadores actuales = los que aparecen en la última jornada
    current_players = gw_last["NombreJugador"].unique() if not gw_last.empty else []

    # Mejor/peor actual — suma de puntos en la temporada, solo jugadores actuales
    if not gw_last.empty and len(current_players) > 0:
        pts_current = (
            gw_manager[gw_manager["NombreJugador"].isin(current_players)]
            .groupby("NombreJugador")["Puntos"]
            .sum()
        )
        best_name = pts_current.idxmax()
        worst_name = pts_current.idxmin()
        best_row = gw_last[gw_last["NombreJugador"] == best_name].iloc[0]
        worst_row = gw_last[gw_last["NombreJugador"] == worst_name].iloc[0]
        best_player = player_dict(best_row, points_override=int(pts_current[best_name]))
        worst_player = player_dict(worst_row, points_override=int(pts_current[worst_name]))
    else:
        best_player = {"name": "Sin datos", "team": None, "position": None, "points": 0}
        worst_player = {"name": "Sin datos", "team": None, "position": None, "points": 0}

    # Mercado
    df_m = df_clean[(df_clean["equipo"] == manager) & (df_clean["type"] == "transfer")]
    market_mercado = int(df_m[df_m["subtype"] == "mercado"].shape[0])
    market_clausulas = int(df_clausulas[df_clausulas["a_equipo"] == manager].shape[0])
    market_acuerdos = int(df_m[df_m["subtype"] == "acuerdo"].shape[0])
    market_spend = round2(abs(df_m[df_m["compra-venta"] == "compra"]["ganancias"].sum()))
    transfer_count = int(df_m.shape[0])

    managers_data.append({
        "name": manager,
        "position": position,
        "totalPoints": total_pts,
        "weekPoints": week_pts,
        "average": avg,
        "stdDev": std,
        "goals": goals,
        "assists": assists,
        "redCards": red_cards,
        "bestPlayer": best_player,
        "worstPlayer": worst_player,
        "bestPlayerHistoric": best_player_historic,
        "transferCount": transfer_count,
        "marketSpend": market_spend,
        "market": {
            "mercado": market_mercado,
            "clausulas": market_clausulas,
            "acuerdos": market_acuerdos,
        },
        "form": form,
        "comparison": {},  # legacy — no se usa en el front nuevo
    })


# ── 8. Noticias ──────────────────────────────────────────────────────────────

logger.info("Cargando noticias...")

news = []
news_dir = ROOT_DIR / json_news_dir
for json_file in sorted(news_dir.glob("*_json.json"), reverse=True):
    data = safe_read_json(str(json_file))
    if not data:
        continue
    cards_file = json_file.parent / json_file.name.replace("_json.json", "_cards.json")
    cards_data = safe_read_json(str(cards_file)) if cards_file.exists() else {}
    cards = cards_data.get("cards", []) if cards_data else []

    date_str = json_file.stem.replace("_json", "")
    clasificacion_card = next((c for c in cards if c.get("tipo") == "clasificacion"), {})

    news.append({
        "date": date_str,
        "title": clasificacion_card.get("titulo", "Sin titular"),
        "subtitle": clasificacion_card.get("subtitulo", ""),
        "summary": " ".join(clasificacion_card.get("texto", [])),
        "cards": [
            {
                "type": c.get("tipo"),
                "title": c.get("titulo"),
                "subtitle": c.get("subtitulo"),
                "manager": c.get("manager"),
                "player": c.get("jugador"),
                "points": c.get("puntos"),
                "money": c.get("dinero"),
                "team": c.get("equipo"),
                "text": c.get("texto", []),
            }
            for c in cards
        ],
    })


# ── 9. Ensamblar y guardar ───────────────────────────────────────────────────

logger.info("Ensamblando app-data.json...")

# Mapa nombre → foto_url desde jugadores.csv
players_map = {}
df_jugadores = safe_read_csv("data/processed/jugadores.csv")
if df_jugadores is not None and not df_jugadores.empty:
    players_map = dict(zip(df_jugadores["nombre"], df_jugadores["foto_url"]))
    logger.info("🖼️  Mapa de jugadores cargado: %d entradas.", len(players_map))

app_data = {
    "generatedAt": datetime.now().isoformat(timespec="seconds"),
    "league": {
        "name": "Sotano League",
        "season": "Temporada 2026",
        "dateRange": f"{df_clean['fecha'].min().date()} · {df_clean['fecha'].max().date()}",
        "standings": standings,
        "poolStandings": pool_standings,
        "managerOfMonth": manager_of_month,
        "playerOfMonth": player_of_month,
        "latestHeadline": latest_headline,
        "mostExpensiveBuy": most_expensive_buy,
        "mostExpensiveClause": most_expensive_clause,
        "mostClausesGiven": most_clauses_given,
        "mostClausesReceived": most_clauses_received,
        "topClauses": top_clauses,
        "topTransfers": top_transfers,
    },
    "managers": managers_data,
    "news": news,
    "playersMap": players_map,
}

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(app_data, f, ensure_ascii=False, indent=2, default=str)

logger.info(f"✅ app-data.json generado en {OUTPUT_PATH}")
logger.info(
    f"   {len(standings)} managers · {len(news)} noticias · "
    f"{len(top_clauses)} clausulazos (30d) · {len(top_transfers)} fichajes (30d)"
)
