"""
Calendario de jornadas y partidos a partir del JSON de /ajax/sw/gameweek.

El endpoint (POST post=gameweek[&id=<id_gameweek>]) devuelve:
  - data.gameweeks: todas las jornadas de la temporada con su estado
    (finished / ongoing / unstarted) y fechas del primer/último partido.
  - data.games: los partidos de la jornada pedida, con estado
    (played / fixture), fecha real (ts) y goles.

Esto permite saber qué partidos *deberían* existir — en particular los
aplazados (una jornada sigue 'ongoing' hasta que se juega su último
partido, aunque sea un mes después) — y elegir qué jornadas re-scrapear
cada día en vez de leer solo la que muestra la web.
"""
import logging
from datetime import date, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

TZ = "Europe/Madrid"

CALENDARIO_COLUMNS = ["id_gameweek", "jornada", "tipo", "estado", "primer_partido", "ultimo_partido"]
PARTIDOS_COLUMNS = [
    "id_partido", "id_gameweek", "jornada", "id_local", "id_visitante",
    "local", "visitante", "goles_local", "goles_visitante", "estado", "fecha", "hora",
]

# Días tras el último partido de una jornada durante los que se sigue
# re-scrapeando, para recoger correcciones de puntos que Mister aplica
# a posteriori (detectadas en la auditoría de 2026-10).
DIAS_REVISION = 7


def _data(payload: dict) -> dict:
    """Acepta la respuesta completa ({"status", "data"}) o solo su `data`."""
    if not isinstance(payload, dict):
        return {}
    return payload.get("data", payload)


def parse_calendario(payload: dict) -> pd.DataFrame:
    """Lista de jornadas de la temporada (data.gameweeks)."""
    filas = []
    for gw in _data(payload).get("gameweeks") or []:
        try:
            filas.append({
                "id_gameweek": int(gw["id"]),
                "jornada": int(gw["gameweek"]),
                "tipo": gw.get("type"),
                "estado": gw.get("status"),
                "primer_partido": gw.get("firstMatchDate"),
                "ultimo_partido": gw.get("lastMatchDate"),
            })
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Jornada del calendario ignorada (%s): %s", e, gw)
    return pd.DataFrame(filas, columns=CALENDARIO_COLUMNS)


def _goles(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None  # '-' en partidos sin jugar


def parse_partidos(payload: dict) -> pd.DataFrame:
    """Partidos de la jornada pedida (data.games), con la fecha real en hora de Madrid."""
    data = _data(payload)
    status = data.get("gameweekStatus") or {}
    filas = []
    for g in data.get("games") or []:
        try:
            ts = (g.get("date") or {}).get("ts")
            local = pd.Timestamp(ts, unit="s", tz="UTC").tz_convert(TZ) if ts else None
            filas.append({
                "id_partido": int(g["id"]),
                "id_gameweek": int(g.get("id_gameweek") or status.get("id")),
                "jornada": int(status["gameweek"]) if status.get("gameweek") is not None else None,
                "id_local": int(g["id_home"]),
                "id_visitante": int(g["id_away"]),
                "local": g.get("home"),
                "visitante": g.get("away"),
                "goles_local": _goles(g.get("goals_home")),
                "goles_visitante": _goles(g.get("goals_away")),
                "estado": g.get("status"),
                "fecha": local.strftime("%Y-%m-%d") if local is not None else None,
                "hora": local.strftime("%H:%M") if local is not None else None,
            })
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Partido ignorado (%s): %s", e, g.get("id"))
    df = pd.DataFrame(filas, columns=PARTIDOS_COLUMNS)
    # El número de jornada viene en gameweekStatus; si faltara, se puede
    # deducir del texto "Jornada N" de cada partido.
    if df["jornada"].isna().any():
        texto = pd.Series([g.get("gameweek", "") for g in data.get("games") or []])
        df["jornada"] = df["jornada"].fillna(texto.str.extract(r"(\d+)")[0].astype(float))
    return df


def merge_partidos(df_viejo: pd.DataFrame, df_nuevo: pd.DataFrame) -> pd.DataFrame:
    """Upsert por id_partido: lo recién scrapeado sustituye a lo guardado."""
    if df_nuevo is None or df_nuevo.empty:
        return df_viejo.copy() if df_viejo is not None else pd.DataFrame(columns=PARTIDOS_COLUMNS)
    if df_viejo is None or df_viejo.empty or "id_partido" not in df_viejo.columns:
        return df_nuevo.copy()
    viejo = df_viejo[~df_viejo["id_partido"].isin(df_nuevo["id_partido"])]
    return pd.concat([viejo, df_nuevo], ignore_index=True)[df_nuevo.columns].sort_values(
        ["jornada", "fecha", "hora", "id_partido"], na_position="last"
    ).reset_index(drop=True)


def seleccionar_jornadas(
    calendario: pd.DataFrame,
    jornadas_descargadas: set | None = None,
    hoy: date | None = None,
    dias_revision: int = DIAS_REVISION,
) -> list[int]:
    """
    Devuelve los id_gameweek a scrapear hoy:
      - toda jornada 'ongoing' (incluye las que tienen un aplazado pendiente);
      - toda jornada 'finished' cuyo último partido fue hace <= dias_revision
        días (correcciones de puntos);
      - toda jornada 'finished' que nunca se ha descargado completa
        (jornada ∉ jornadas_descargadas) — sirve también de backfill.
    Las 'unstarted' nunca se piden: no tienen datos.
    """
    if calendario is None or calendario.empty:
        return []
    hoy = hoy or date.today()
    limite = pd.Timestamp(hoy - timedelta(days=dias_revision))
    descargadas = set(jornadas_descargadas or ())

    ids = []
    for _, gw in calendario.iterrows():
        estado = gw["estado"]
        ultimo = pd.to_datetime(gw["ultimo_partido"], errors="coerce")
        if estado == "ongoing":
            ids.append(int(gw["id_gameweek"]))
        elif estado == "finished" and (
            (pd.notna(ultimo) and ultimo.normalize() >= limite)
            or int(gw["jornada"]) not in descargadas
        ):
            ids.append(int(gw["id_gameweek"]))
    return ids


def anotar_fecha_partido(df_gameweek: pd.DataFrame, partidos: pd.DataFrame) -> pd.DataFrame:
    """
    Sustituye `Date` (día del scrape) por la fecha real del partido,
    cruzando por (Jornada, EquipoLocal, EquipoVisitante). Si un partido no
    está en `partidos`, conserva la fecha que traía.
    """
    if df_gameweek is None or df_gameweek.empty or partidos is None or partidos.empty:
        return df_gameweek
    fechas = (
        partidos.dropna(subset=["fecha"])
        .rename(columns={"jornada": "Jornada", "id_local": "EquipoLocal", "id_visitante": "EquipoVisitante"})
        [["Jornada", "EquipoLocal", "EquipoVisitante", "fecha"]]
        .astype({"Jornada": int, "EquipoLocal": int, "EquipoVisitante": int})
        .drop_duplicates(["Jornada", "EquipoLocal", "EquipoVisitante"], keep="last")
    )
    out = df_gameweek.merge(fechas, on=["Jornada", "EquipoLocal", "EquipoVisitante"], how="left")
    out["Date"] = out["fecha"].fillna(out["Date"])
    return out.drop(columns="fecha")
