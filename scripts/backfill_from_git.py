"""
Recupera días perdidos en la BD a partir de los CSVs de una versión anterior
del repo (antes de la migración a SQLite los datos se commiteaban como CSV
en data/processed/).

Caso que lo motivó: la migración del 20/08/2026 no incluyó los días 17, 18
y 20 de agosto, que sí están en el commit af1cd55. Ver
docs/roadmap_calidad_datos.md (Fase 0.3).

- Tablas por snapshot diario (mercado, subidasBajadas, jornadas): se añaden
  las filas de los días del rango que no existen en la BD.
- ganancias: los traspasos ya están en la BD pero con la fecha del día en
  que se volvieron a leer; se corrige `date` por idTransfer si la del CSV
  es anterior.

Idempotente: una segunda ejecución no cambia nada. Tras aplicarlo hay que
ejecutar scripts/run_preprocess.py para regenerar las tablas derivadas
(ganancias_clean, ganancias_jugador, clausulas_acuerdos).

Uso:
    python scripts/backfill_from_git.py af1cd55 2026-08-17 2026-08-20 [--apply]
Sin --apply solo muestra lo que haría.
"""
import argparse
import io
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.utils import db as db_utils

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SNAPSHOT_TABLES = ["mercado", "subidasBajadas", "jornadas"]


def csv_en_commit(commit: str, tabla: str) -> pd.DataFrame:
    out = subprocess.run(
        ["git", "show", f"{commit}:data/processed/{tabla}.csv"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT_DIR,
    )
    if out.returncode != 0:
        logger.warning("%s no existe en %s", tabla, commit)
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(out.stdout))


def backfill_snapshots(commit, desde, hasta, temporada, apply):
    cambios = 0
    for tabla in SNAPSHOT_TABLES:
        git = csv_en_commit(commit, tabla)
        if git.empty:
            continue
        git["date"] = git["date"].astype(str).str[:10]
        git = git[(git["date"] >= desde) & (git["date"] <= hasta)]
        bd = db_utils.read_table(tabla, temporada=temporada)
        dias_en_bd = set(bd["date"].astype(str).str[:10]) if not bd.empty else set()
        nuevas = git[~git["date"].isin(dias_en_bd)]
        logger.info("%s: %d filas nuevas (días %s)", tabla, len(nuevas), sorted(nuevas["date"].unique()))
        if apply and not nuevas.empty:
            combinado = pd.concat([bd.drop(columns="temporada", errors="ignore"), nuevas], ignore_index=True)
            combinado = combinado.sort_values("date", kind="stable").reset_index(drop=True)
            db_utils.write_table(combinado, tabla, temporada)
        cambios += len(nuevas)
    return cambios


def corregir_fechas_ganancias(commit, desde, hasta, temporada, apply):
    git = csv_en_commit(commit, "ganancias")
    if git.empty:
        return 0
    git = git[(git["type"] == "transfer") & git["idTransfer"].notna()]
    git["date"] = git["date"].astype(str).str[:10]
    git = git[(git["date"] >= desde) & (git["date"] <= hasta)]
    fecha_real = git.drop_duplicates("idTransfer").set_index("idTransfer")["date"]

    bd = db_utils.read_table("ganancias", temporada=temporada)
    mask = bd["idTransfer"].isin(fecha_real.index)
    mask &= bd["date"].astype(str).str[:10] > bd["idTransfer"].map(fecha_real).fillna("9999")
    logger.info("ganancias: %d traspasos con fecha corregible (%s)",
                int(mask.sum()), bd.loc[mask, "date"].value_counts().to_dict())
    if apply and mask.any():
        bd.loc[mask, "date"] = bd.loc[mask, "idTransfer"].map(fecha_real)
        db_utils.write_table(bd.drop(columns="temporada"), "ganancias", temporada)
    return int(mask.sum())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("commit")
    p.add_argument("desde", help="YYYY-MM-DD (incluido)")
    p.add_argument("hasta", help="YYYY-MM-DD (incluido)")
    p.add_argument("--temporada", default=None)
    p.add_argument("--apply", action="store_true", help="escribir en la BD (por defecto solo muestra)")
    a = p.parse_args()
    temporada = a.temporada or db_utils.get_active_season()

    n = backfill_snapshots(a.commit, a.desde, a.hasta, temporada, a.apply)
    n += corregir_fechas_ganancias(a.commit, a.desde, a.hasta, temporada, a.apply)
    logger.info("%s %d cambios.", "Aplicados" if a.apply else "Se aplicarían", n)


if __name__ == "__main__":
    main()
