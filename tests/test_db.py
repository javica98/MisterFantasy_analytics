"""
Tests para src/utils/db.py — capa de acceso a data/mister.db (SQLite),
particionada por columna `temporada`.
"""
import pandas as pd
import pytest

from src.utils import db as db_utils


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Redirige get_db_path() a un SQLite temporal, aislado del data/mister.db real."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(db_utils, "get_db_path", lambda: path)
    return path


class TestGetConnection:
    def test_crea_el_archivo_y_el_directorio_padre(self, tmp_path, monkeypatch):
        nested = tmp_path / "nested" / "mister.db"
        monkeypatch.setattr(db_utils, "get_db_path", lambda: nested)
        conn = db_utils.get_connection()
        conn.close()
        assert nested.exists()


class TestTableExists:
    def test_tabla_inexistente_devuelve_false(self, db_path):
        conn = db_utils.get_connection()
        assert db_utils.table_exists(conn, "no_existe") is False
        conn.close()

    def test_tabla_existente_devuelve_true(self, db_path):
        conn = db_utils.get_connection()
        conn.execute("CREATE TABLE gameweek (temporada TEXT)")
        assert db_utils.table_exists(conn, "gameweek") is True
        conn.close()


class TestReadTable:
    def test_tabla_inexistente_devuelve_dataframe_vacio(self, db_path):
        df = db_utils.read_table("no_existe")
        assert df.empty

    def test_lee_solo_la_temporada_pedida(self, db_path):
        db_utils.write_table(pd.DataFrame([{"jornada": 1, "puntos": 10}]), "clasificaciones", "2025-26")
        db_utils.write_table(pd.DataFrame([{"jornada": 1, "puntos": 99}]), "clasificaciones", "2026-27")

        out_vieja = db_utils.read_table("clasificaciones", temporada="2025-26")
        out_nueva = db_utils.read_table("clasificaciones", temporada="2026-27")

        assert out_vieja["puntos"].tolist() == [10]
        assert out_nueva["puntos"].tolist() == [99]

    def test_sin_temporada_devuelve_todas(self, db_path):
        db_utils.write_table(pd.DataFrame([{"x": 1}]), "t", "2025-26")
        db_utils.write_table(pd.DataFrame([{"x": 2}]), "t", "2026-27")
        out = db_utils.read_table("t")
        assert sorted(out["x"].tolist()) == [1, 2]


class TestWriteTable:
    def test_es_idempotente(self, db_path):
        df = pd.DataFrame([{"jornada": 1}, {"jornada": 2}])
        db_utils.write_table(df, "gameweek", "2026-27")
        db_utils.write_table(df, "gameweek", "2026-27")
        out = db_utils.read_table("gameweek", temporada="2026-27")
        assert len(out) == 2

    def test_no_afecta_a_otras_temporadas(self, db_path):
        db_utils.write_table(pd.DataFrame([{"x": 1}]), "t", "2025-26")
        db_utils.write_table(pd.DataFrame([{"x": 2}, {"x": 3}]), "t", "2026-27")
        db_utils.write_table(pd.DataFrame([{"x": 9}]), "t", "2026-27")  # sobreescribe solo 2026-27

        out_vieja = db_utils.read_table("t", temporada="2025-26")
        out_nueva = db_utils.read_table("t", temporada="2026-27")

        assert out_vieja["x"].tolist() == [1]
        assert out_nueva["x"].tolist() == [9]

    def test_anade_columna_temporada(self, db_path):
        df = pd.DataFrame([{"jornada": 1}])
        db_utils.write_table(df, "t", "2026-27")
        out = db_utils.read_table("t")
        assert "temporada" in out.columns
        assert out["temporada"].tolist() == ["2026-27"]

    def test_no_duplica_columna_temporada_si_ya_viene_en_el_df(self, db_path):
        # write_table debe sobreescribir temporada, no añadirla dos veces
        df = pd.DataFrame([{"jornada": 1, "temporada": "otra-cosa"}])
        db_utils.write_table(df, "t", "2026-27")
        out = db_utils.read_table("t", temporada="2026-27")
        assert list(out.columns).count("temporada") == 1
        assert out["temporada"].tolist() == ["2026-27"]


class TestKnownTables:
    def test_incluye_las_tablas_de_config_yaml(self):
        tables = db_utils.known_tables()
        assert "gameweek" in tables
        assert "clasificaciones" in tables
        assert "mercado" in tables

    def test_excluye_test_csv(self):
        assert "test" not in db_utils.known_tables()


class TestGetActiveSeason:
    def test_devuelve_un_string_no_vacio(self):
        season = db_utils.get_active_season()
        assert isinstance(season, str) and season
