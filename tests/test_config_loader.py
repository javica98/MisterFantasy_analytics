"""
Tests unitarios para src/utils/config_loader.py
Cubre: get_base_dir, resolve_path, load_config (con env variables mockeadas)
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.config_loader import get_base_dir, load_config, resolve_path


# ─────────────────────────────────────────────
# get_base_dir
# ─────────────────────────────────────────────

class TestGetBaseDir:
    def test_devuelve_path(self):
        result = get_base_dir()
        assert isinstance(result, Path)

    def test_es_directorio_existente(self):
        result = get_base_dir()
        assert result.exists()
        assert result.is_dir()

    def test_contiene_src(self):
        result = get_base_dir()
        assert (result / "src").exists()


# ─────────────────────────────────────────────
# resolve_path
# ─────────────────────────────────────────────

class TestResolvePath:
    def test_resuelve_clave_simple(self):
        cfg = {"paths": {"data": "data/processed"}}
        result = resolve_path(cfg, "paths", "data")
        assert isinstance(result, Path)
        assert str(result).endswith(str(Path("data/processed")))

    def test_path_absoluto_sin_prefijo(self):
        cfg = {"paths": {"img": "/absolute/path"}}
        result = resolve_path(cfg, "paths", "img")
        assert result.is_absolute()

    def test_clave_inexistente_lanza_error(self):
        cfg = {"paths": {}}
        with pytest.raises((KeyError, TypeError)):
            resolve_path(cfg, "paths", "no_existe")


# ─────────────────────────────────────────────
# load_config
# ─────────────────────────────────────────────

class TestLoadConfig:
    def test_devuelve_dict(self):
        result = load_config(validate_env=False)
        assert isinstance(result, dict)

    def test_tiene_seccion_paths(self):
        result = load_config(validate_env=False)
        assert "paths" in result

    def test_tiene_seccion_env(self):
        result = load_config(validate_env=False)
        assert "env" in result

    def test_tiene_seccion_data(self):
        result = load_config(validate_env=False)
        assert "data" in result

    def test_env_vars_cargadas_desde_config(self):
        result = load_config(validate_env=False)
        env = result["env"]
        # Deben existir como claves aunque estén vacías
        assert "GEMINI_API_KEY" in env or "GROQ_API_KEY" in env

    def test_validate_env_true_con_vars_presentes(self):
        """No debe lanzar si todas las vars de entorno están."""
        # Nuestro config/.env las tiene, así que no debe fallar
        try:
            result = load_config(validate_env=True)
            assert result is not None
        except EnvironmentError:
            pytest.skip("Variables de entorno no disponibles en este entorno")

    def test_validate_env_true_sin_vars_lanza_error(self):
        """Si faltan vars de entorno, debe lanzar EnvironmentError."""
        # Parcheamos os.getenv para que todas las vars críticas devuelvan None
        with patch("src.utils.config_loader.os.getenv", return_value=None):
            with pytest.raises(EnvironmentError, match="Faltan variables de entorno"):
                load_config(validate_env=True)
