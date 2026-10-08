"""
Validación de los datos de la temporada activa en data/mister.db.

Se ejecuta en el workflow diario después de la extracción. Antes de esto el
job salía en verde aunque faltaran días, partidos o jornadas enteras (ver
docs/roadmap_calidad_datos.md). Si hay errores, termina con código 1 para
que el job falle y se abra el issue automático.

Uso:
    python scripts/validate_data.py [--baseline ruta/a/mister_antes.db] [--hoy YYYY-MM-DD]

--baseline: copia de la BD antes de la extracción, para detectar tablas que
            pierden filas.

Escribe un resumen en Markdown en stdout y, si existe, en $GITHUB_STEP_SUMMARY.
"""
import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.utils import db as db_utils
from src.utils.config_loader import load_config

SNAPSHOT_TABLES = ["mercado", "subidasBajadas", "jornadas"]

# Claves que identifican una fila; None = la fila completa (sin las columnas
# de metadatos, que cambian en cada run aunque el dato sea el mismo).
METADATOS = {"scraped_at", "created", "temporada"}
DUP_KEYS = {
    "partidos_stats": ["id_partido", "clave"],
    "once_ideal": ["jornada", "orden"],
    "alineaciones_probables": ["id_partido", "id_equipo", "orden"],
    "gameweek": ["Jornada", "EquipoLocal", "EquipoVisitante", "Manager", "NombreJugador"],
    "clasificaciones": ["jornada", "nombre"],
    "quiniela": ["jornada", "nombre"],
    "partidos": ["id_partido"],
    "calendario": ["id_gameweek"],
    "jornadas": ["date", "jornada"],
    "mercado": None,
    "subidasBajadas": None,
}


@dataclass
class Informe:
    errores: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    ok: list = field(default_factory=list)

    def error(self, msg):
        self.errores.append(msg)

    def aviso(self, msg):
        self.avisos.append(msg)

    def bien(self, msg):
        self.ok.append(msg)

    def markdown(self, temporada) -> str:
        estado = "❌ Con errores" if self.errores else ("⚠️ Con avisos" if self.avisos else "✅ Todo correcto")
        lineas = [f"## Validación de datos {temporada}: {estado}", ""]
        for titulo, items, icono in (("Errores", self.errores, "❌"), ("Avisos", self.avisos, "⚠️"),
                                     ("Correcto", self.ok, "✅")):
            if items:
                lineas += [f"### {titulo}", *[f"- {icono} {m}" for m in items], ""]
        return "\n".join(lineas)


def leer(conn, tabla, temporada) -> pd.DataFrame:
    if not db_utils.table_exists(conn, tabla):
        return pd.DataFrame()
    return pd.read_sql_query(f"SELECT * FROM {tabla} WHERE temporada = ?", conn, params=(temporada,))


def check_continuidad(conn, temporada, hoy, dias_perdidos, max_dias_sin_datos, inf: Informe):
    for tabla in SNAPSHOT_TABLES:
        df = leer(conn, tabla, temporada)
        if df.empty:
            inf.error(f"`{tabla}`: sin datos en la temporada")
            continue
        fechas = set(df["date"].astype(str).str[:10])
        rango = pd.date_range(min(fechas), max(fechas)).strftime("%Y-%m-%d")
        faltan = sorted(set(rango) - fechas - set(dias_perdidos))
        if faltan:
            inf.error(f"`{tabla}`: faltan {len(faltan)} día(s): {', '.join(faltan)}")
        else:
            inf.bien(f"`{tabla}`: un registro por día desde {min(fechas)} ({len(fechas)} días)")

        retraso = (hoy - date.fromisoformat(max(fechas))).days
        if retraso > max_dias_sin_datos:
            inf.error(f"`{tabla}`: el último dato es del {max(fechas)} ({retraso} días sin datos)")


def check_gameweek_vs_calendario(conn, temporada, inf: Informe):
    partidos = leer(conn, "partidos", temporada)
    gw = leer(conn, "gameweek", temporada)
    if partidos.empty:
        inf.aviso("`partidos` vacía: no se puede contrastar `gameweek` con el calendario")
        return
    jugados = partidos[partidos["estado"] == "played"]
    con_datos = set(zip(gw["Jornada"], gw["EquipoLocal"], gw["EquipoVisitante"])) if not gw.empty else set()

    faltan = jugados[[
        (j, loc, vis) not in con_datos
        for j, loc, vis in zip(jugados["jornada"], jugados["id_local"], jugados["id_visitante"])
    ]]
    for jornada, grupo in faltan.groupby("jornada"):
        detalle = ", ".join(f"{r.local}–{r.visitante} ({r.fecha})" for r in grupo.itertuples())
        inf.error(f"`gameweek` J{int(jornada)}: {len(grupo)} partido(s) jugado(s) sin datos: {detalle}")
    if faltan.empty:
        inf.bien(f"`gameweek`: los {len(jugados)} partidos jugados según el calendario tienen datos")

    pendientes = partidos[(partidos["estado"] != "played")]
    calendario = leer(conn, "calendario", temporada)
    iniciadas = set(calendario.loc[calendario["estado"] != "unstarted", "jornada"]) if not calendario.empty else set()
    aplazados = pendientes[pendientes["jornada"].isin(iniciadas)]
    for r in aplazados.itertuples():
        inf.aviso(f"Aplazado pendiente: J{int(r.jornada)} {r.local}–{r.visitante} ({r.fecha} {r.hora})")


def check_clasificaciones(conn, temporada, inf: Informe):
    calendario = leer(conn, "calendario", temporada)
    clas = leer(conn, "clasificaciones", temporada)
    if calendario.empty:
        inf.aviso("`calendario` vacío: no se puede contrastar `clasificaciones`")
        return
    managers = clas.groupby("jornada")["nombre"].nunique() if not clas.empty else pd.Series(dtype=int)
    esperado = int(managers.max()) if not managers.empty else 0
    terminadas = sorted(calendario.loc[calendario["estado"] == "finished", "jornada"].astype(int))
    faltan = [j for j in terminadas if j not in managers.index]
    incompletas = [f"J{j} ({managers[j]}/{esperado})" for j in terminadas
                   if j in managers.index and managers[j] < esperado]
    if faltan:
        inf.error(f"`clasificaciones`: faltan jornadas terminadas: {', '.join(f'J{j}' for j in faltan)}")
    if incompletas:
        inf.error(f"`clasificaciones`: jornadas con managers de menos: {', '.join(incompletas)}")
    if not faltan and not incompletas:
        inf.bien(f"`clasificaciones`: {len(terminadas)} jornadas terminadas con {esperado} managers cada una")


def check_duplicados(conn, temporada, inf: Informe):
    con_dups = []
    for tabla, clave in DUP_KEYS.items():
        df = leer(conn, tabla, temporada)
        if df.empty:
            continue
        clave = clave or [c for c in df.columns if c not in METADATOS]
        n = int(df.duplicated(subset=clave).sum())
        if n:
            con_dups.append(f"`{tabla}` ({n})")
    if con_dups:
        inf.error(f"Filas duplicadas: {', '.join(con_dups)}")
    else:
        inf.bien("Sin duplicados por clave")


def check_encogimiento(conn, baseline: Path, temporada, inf: Informe):
    with sqlite3.connect(baseline) as base:
        for (tabla,) in base.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            if not db_utils.table_exists(conn, tabla):
                inf.error(f"`{tabla}`: la tabla ha desaparecido")
                continue
            antes = base.execute(f"SELECT COUNT(*) FROM {tabla} WHERE temporada = ?", (temporada,)).fetchone()[0]
            ahora = conn.execute(f"SELECT COUNT(*) FROM {tabla} WHERE temporada = ?", (temporada,)).fetchone()[0]
            if ahora < antes:
                inf.error(f"`{tabla}`: ha perdido filas ({antes} → {ahora})")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", type=Path, default=None)
    p.add_argument("--hoy", type=date.fromisoformat, default=date.today())
    a = p.parse_args()

    cfg = load_config(validate_env=False)
    vcfg = cfg.get("validation", {})
    temporada = db_utils.get_active_season()
    inf = Informe()

    with db_utils.get_connection() as conn:
        check_continuidad(conn, temporada, a.hoy, vcfg.get("dias_perdidos", []),
                          vcfg.get("max_dias_sin_datos", 1), inf)
        check_gameweek_vs_calendario(conn, temporada, inf)
        check_clasificaciones(conn, temporada, inf)
        check_duplicados(conn, temporada, inf)
        if a.baseline:
            if a.baseline.exists():
                check_encogimiento(conn, a.baseline, temporada, inf)
            else:
                inf.aviso(f"No existe la BD de referencia {a.baseline}")

    md = inf.markdown(temporada)
    print(md)
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    return 1 if inf.errores else 0


if __name__ == "__main__":
    sys.exit(main())
