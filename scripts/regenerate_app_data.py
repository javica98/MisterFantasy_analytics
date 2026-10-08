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
from PIL import Image

# ── Entorno ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.utils import db as db_utils
from src.utils.config_loader import load_config
from src.utils.file_utils import safe_read_csv
from src.utils.team_map import map_position, map_team


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
NEWS_JSON_DIR     = ROOT / "newspaper" / "json"
OUTPUT_PATH       = ROOT / "web" / "data" / "app-data.json"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
# Miniaturas de portada para el carrusel de Noticias. Viven dentro de web/
# para que entren en la imagen Docker (newspaper/ y archive/ se excluyen) y
# pesan ~15 KB en vez del PNG de página completa (~1,2 MB).
COVERS_DIR    = ROOT / "web" / "covers"
COVER_DEFAULT_SRC = ROOT / "newspaper" / "photos" / "Portada_Jornada.jpg"
COVER_WIDTH   = 240  # 2x del ancho CSS (96px) de .jornada-cover
COVER_LARGE_WIDTH = 900  # portada protagonista de Noticias/Home (y su zoom)

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


def _position_name(value) -> str:
    """ID de posición (1-4, a veces como float/str desde la BD) -> nombre."""
    try:
        return str(map_position(int(float(value))))
    except (TypeError, ValueError):
        return _safe_str(value)


def _load_players() -> pd.DataFrame:
    """Jugadores (nombre -> foto) de todas las temporadas, quedándose con la
    fila más reciente de cada nombre. La tabla `jugadores` solo se rellena
    con run_players_db.py, que no corre en el workflow diario: al empezar
    temporada nueva no tenía filas para ella y el script entero salía con
    error (por eso app-data.json se quedó congelado en julio). Las fotos no
    dependen de la temporada, así que vale con la última conocida."""
    df = db_utils.read_table("jugadores")
    if df.empty:
        logger.warning("Sin datos de jugadores: la web mostrará iniciales en vez de fotos")
        return df
    if "temporada" in df.columns:
        df = df.sort_values("temporada").drop_duplicates("nombre", keep="last")
    logger.info("  jugadores: %d filas (todas las temporadas)", len(df))
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

def _ranked(totals: pd.Series) -> dict:
    """{nombre: posición} ordenando por puntos descendente."""
    order = totals.sort_values(ascending=False).index
    return {name: i + 1 for i, name in enumerate(order)}


def build_standings(df_clas: pd.DataFrame) -> list:
    """Clasificación acumulada. Cada fila lleva también la posición que tenía
    en la actualización anterior (`prevRank`, para las flechas de
    subida/bajada). Ojo: `clasificaciones` no tiene una fila por jornada (hay
    huecos entre capturas), así que prevRank compara con la captura previa,
    no necesariamente con la jornada anterior."""
    total = df_clas.groupby("nombre")["puntos"].sum().sort_values(ascending=False)
    prev_rank = {}
    if "jornada" in df_clas.columns and df_clas["jornada"].nunique() > 1:
        last = df_clas["jornada"].max()
        before = df_clas[df_clas["jornada"] != last].groupby("nombre")["puntos"].sum()
        prev_rank = _ranked(before.reindex(total.index, fill_value=0))
    return [
        {
            "rank": i + 1,
            "manager": name,
            "points": int(points),
            "prevRank": prev_rank.get(name),
        }
        for i, (name, points) in enumerate(total.items())
    ]


def build_pool_standings(df_quin: pd.DataFrame) -> list:
    """Clasificación de quinielas acumulada (mismo formato que build_standings)."""
    return build_standings(df_quin)


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
                "position": _position_name(best_idx[2]),
                "points":   int(pts_jugador[best_idx]),
            }
            # mejor esta temporada (mismo que historic, pero lo dejamos igual)
            best_player = best_historic.copy()

            worst_idx = pts_jugador.idxmin()
            worst_player = {
                "name":     worst_idx[0],
                "team":     map_team(worst_idx[1]),
                "position": _position_name(worst_idx[2]),
                "points":   int(pts_jugador[worst_idx]),
            }

        # mercado
        compras  = df_t[df_t["compra-venta"] == "compra"]
        clausulas = compras[compras["subtype"] == "clausula"]
        acuerdos  = compras[compras["subtype"] == "acuerdo"]
        mercado_c = compras[compras["subtype"] == "mercado"]

        market_spend = round(float(compras["ganancias"].abs().sum()), 2)

        # form: puntos de las últimas N jornadas (para el badge de variación)
        form = [int(pts_jornada.get(j, 0)) for j in form_jornadas]
        # seasonForm: puntos de cada jornada 1..última, indexado por número de
        # jornada (posición i = jornada i+1). Las jornadas que faltan en la BD
        # van como null: antes se compactaban y, si faltaba una (p.ej. la J37
        # de 2025-26), la web etiquetaba la J38 como "Jornada 37".
        played = set(int(j) for j in all_jornadas)
        season_form = [
            int(pts_jornada.get(j, 0)) if j in played else None
            for j in range(1, last_jornada + 1)
        ]

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
            "seasonForm": season_form,
            "comparison": {},
        })

    logger.info("Managers procesados: %d", len(managers))
    return managers


# ─────────────────────────────────────────────────────────────────────────────
# Sección: managers por temporada (para el desplegable de año en Estadísticas)
# ─────────────────────────────────────────────────────────────────────────────

def list_available_seasons() -> list:
    """Temporadas con datos reales en la BD (columna `temporada` de gameweek)."""
    df = db_utils.read_table("gameweek")
    if df.empty or "temporada" not in df.columns:
        return [SEASON]
    seasons = sorted(df["temporada"].unique().tolist())
    return seasons or [SEASON]


def build_managers_for_season(season: str) -> list:
    """Igual que build_managers(), pero leyendo directo de la BD para una
    temporada concreta (no necesariamente la activa)."""
    df_gw   = db_utils.read_table("gameweek", temporada=season)
    df_clas = db_utils.read_table("clasificaciones", temporada=season)
    df_merc = db_utils.read_table("ganancias_clean", temporada=season)

    if df_gw.empty or df_clas.empty:
        logger.warning("Temporada %s sin datos suficientes para managers, se omite", season)
        return []

    df_transfers = df_merc[df_merc["type"] == "transfer"].copy() if not df_merc.empty else df_merc
    standings = build_standings(df_clas)
    return build_managers(df_gw, df_clas, df_transfers, standings)


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
            "team":        map_team(row["EquipoJugador"]),
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
        "lastRound":            last_jornada,
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

def _make_thumbnail(src: Path, dest: Path, width: int = COVER_WIDTH, quality: int = 72) -> bool:
    """Genera `dest` (WebP de `width` px de ancho) desde `src` si falta o si
    `src` es más reciente. Devuelve True si `dest` existe al terminar."""
    if not src.exists():
        return dest.exists()
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return True
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGB")
            height = round(im.height * width / im.width)
            im.resize((width, height), Image.LANCZOS).save(dest, "WEBP", quality=quality, method=6)
        return True
    except Exception as e:
        logger.warning("No se pudo generar miniatura %s: %s", dest.name, e)
        return dest.exists()


def build_default_cover() -> str | None:
    """Miniatura genérica para jornadas sin portada propia."""
    dest = COVERS_DIR / "default.webp"
    return "/web/covers/default.webp" if _make_thumbnail(COVER_DEFAULT_SRC, dest) else None


def _cover_for(covers_src_dir: Path | None, season: str, jornada_num: int) -> tuple[str | None, str | None]:
    """(miniatura, portada grande) de una edición, o None si no hay PNG."""
    if covers_src_dir is None:
        return None, None
    src = covers_src_dir / f"jornada_{jornada_num}_jornada_news.png"
    thumb = COVERS_DIR / season / f"jornada_{jornada_num}.webp"
    large = COVERS_DIR / season / f"jornada_{jornada_num}-large.webp"
    thumb_url = f"/web/covers/{season}/{thumb.name}" if _make_thumbnail(src, thumb) else None
    large_url = (
        f"/web/covers/{season}/{large.name}"
        if _make_thumbnail(src, large, COVER_LARGE_WIDTH, 78) else None
    )
    return thumb_url, large_url


def build_news(news_json_dir: Path, covers_src_dir: Path | None = None, season: str = SEASON) -> list:
    """
    Lee todos los jornada_XX_cards.json desde cards/ y articles/
    y construye la lista de noticias para la web app. Si se pasa
    `covers_src_dir` (carpeta newspaper/new de la temporada), añade a cada
    edición la URL de su miniatura de portada.
    """
    news = []
    articles_dir = news_json_dir / "articles"
    cards_dir = news_json_dir / "cards"

    # Orden numerico por jornada, no alfabetico -> "jornada_9" ordenaba
    # despues de "jornada_38" al comparar como texto ("9" > "3").
    json_files = sorted(
        articles_dir.glob("jornada_*_json.json"),
        key=lambda f: int(f.stem.split("_")[1]),
        reverse=True,
    )

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

            cover, cover_large = _cover_for(covers_src_dir, season, int(jornada_stem.split("_")[1]))
            news.append({
                "date":            jornada_label,
                "cover":           cover,
                "coverLarge":      cover_large,
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


def build_news_for_season(season: str) -> list:
    """Igual que build_news(), pero resolviendo la carpeta correcta: la
    temporada activa vive en newspaper/json/, las archivadas en
    archive/temporada_{season}/newspaper/json/."""
    base = ROOT if season == SEASON else ROOT / "archive" / f"temporada_{season}"
    json_dir = base / "newspaper" / "json"
    if not json_dir.exists():
        logger.warning("Sin carpeta de periódicos para temporada %s (%s)", season, json_dir)
        return []
    return build_news(json_dir, base / "newspaper" / "new", season)


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
    df_jug  = _load_players()

    # Solo transfers
    df_transfers = df_merc[df_merc["type"] == "transfer"].copy()

    logger.info("Construyendo secciones...")

    players_map  = build_players_map(df_jug)
    standings    = build_standings(df_clas)
    pool_stand   = build_pool_standings(df_quin)
    managers     = build_managers(df_gw, df_clas, df_transfers, standings)
    news         = build_news_for_season(SEASON)
    latest_card  = _get_latest_headline(news)
    league       = build_league(df_gw, df_clas, df_transfers, standings, pool_stand, [latest_card] if latest_card else [])

    seasons = list_available_seasons()
    managers_by_season = {}
    news_by_season = {}
    for season in seasons:
        if season == SEASON:
            managers_by_season[season] = managers  # ya calculado arriba, no repetir trabajo
            news_by_season[season] = news
        else:
            managers_by_season[season] = build_managers_for_season(season)
            news_by_season[season] = build_news_for_season(season)
    logger.info("Temporadas disponibles: %s", seasons)

    app_data = {
        "generatedAt":      datetime.now().isoformat(timespec="seconds"),
        "league":           league,
        "managers":         managers,
        "news":             news,
        "playersMap":       players_map,
        "seasons":          seasons,
        "activeSeason":     SEASON,
        "defaultCover":     build_default_cover(),
        "managersBySeason": managers_by_season,
        "newsBySeason":     news_by_season,
    }

    # Compacto (sin indent): la web lo descarga en cada visita y el indentado
    # inflaba el archivo ~30% sin aportar nada.
    OUTPUT_PATH.write_text(
        json.dumps(app_data, ensure_ascii=False, separators=(",", ":"), cls=_NumpyEncoder),
        encoding="utf-8",
    )
    logger.info("app-data.json generado -> %s", OUTPUT_PATH)
    logger.info(
        "  %d managers | %d noticias | %d jugadores en mapa",
        len(managers), len(news), len(players_map),
    )


if __name__ == "__main__":
    main()
