"""
Tests para src/utils/file_utils.py — en particular el enrutado de
safe_read_csv/safe_save_csv hacia data/mister.db (tablas conocidas de
config.yaml) o hacia CSV en disco (fallback legacy).
"""
import pandas as pd
import pytest

from src.utils import db as db_utils
from src.utils import file_utils


@pytest.fixture(autouse=True)
def _reset_known_tables_cache(monkeypatch):
    """El cache de nombres de tabla es un global de módulo; lo reseteamos
    entre tests para que cada uno controle su propio estado."""
    monkeypatch.setattr(file_utils, "_known_tables_cache", None)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(db_utils, "get_db_path", lambda: path)
    monkeypatch.setattr(db_utils, "get_active_season", lambda: "2026-27")
    return path


class TestRutaConocidaVaALaBD:
    def test_safe_save_csv_escribe_en_la_bd(self, db_path):
        df = pd.DataFrame([{"jornada": 1, "puntos": 5}])
        file_utils.safe_save_csv(df, "data/processed/clasificaciones.csv")

        out = db_utils.read_table("clasificaciones", temporada="2026-27")
        assert out["puntos"].tolist() == [5]

    def test_safe_read_csv_lee_de_la_bd_no_del_disco(self, db_path, tmp_path):
        db_utils.write_table(pd.DataFrame([{"puntos": 42}]), "mercado", "2026-27")

        # ruta que apunta a un fichero que no existe en disco: si file_utils
        # cayera al fallback legacy, esto devolvería DataFrame vacío
        ruta_inexistente = str(tmp_path / "no-existe" / "mercado.csv")
        out = file_utils.safe_read_csv(ruta_inexistente)

        assert out["puntos"].tolist() == [42]

    def test_roundtrip_preserva_columnas_originales(self, db_path):
        df = pd.DataFrame([{"fecha": "2026-08-16", "jugador": "K. Mbappé", "ganancias": -8.0}])
        file_utils.safe_save_csv(df, "data/processed/ganancias_clean.csv")
        out = file_utils.safe_read_csv("data/processed/ganancias_clean.csv")

        assert out.loc[0, "jugador"] == "K. Mbappé"
        assert out.loc[0, "ganancias"] == -8.0


class TestRutaDesconocidaUsaCsvLegacy:
    def test_safe_save_y_read_csv_en_disco(self, tmp_path, monkeypatch):
        monkeypatch.setattr(file_utils, "_known_tables_cache", {"gameweek", "clasificaciones"})
        path = tmp_path / "test.csv"  # "test" está explícitamente excluido de las tablas de BD

        file_utils.safe_save_csv(pd.DataFrame([{"a": 1}]), str(path))
        assert path.exists()

        out = file_utils.safe_read_csv(str(path))
        assert out["a"].tolist() == [1]

    def test_ruta_inexistente_y_desconocida_devuelve_vacio(self, tmp_path, monkeypatch):
        monkeypatch.setattr(file_utils, "_known_tables_cache", {"gameweek"})
        out = file_utils.safe_read_csv(str(tmp_path / "no_existe.csv"))
        assert out.empty
