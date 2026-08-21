"""
Tests para src/scraper/login.py — cerrar_popup_publicidad() (extraída para
eliminar la duplicación x3) y los reintentos con backoff de login()
(hallazgo DATA-04).
"""
from unittest.mock import MagicMock, patch

import pytest

from src.scraper.login import cerrar_popup_publicidad, login


class TestCerrarPopupPublicidad:
    def test_cierra_el_popup_si_esta_visible(self):
        page = MagicMock()
        page.locator.return_value.is_visible.return_value = True

        result = cerrar_popup_publicidad(page)

        assert result is True
        page.locator.return_value.click.assert_called_once()

    def test_no_hace_nada_si_no_esta_visible(self):
        page = MagicMock()
        page.locator.return_value.is_visible.return_value = False

        result = cerrar_popup_publicidad(page, intentos=3, espera_ms=0)

        assert result is False
        page.locator.return_value.click.assert_not_called()
        assert page.wait_for_timeout.call_count == 2  # entre los 3 intentos, no tras el último

    def test_no_lanza_excepcion_si_locator_falla(self):
        page = MagicMock()
        page.locator.side_effect = Exception("boom")

        result = cerrar_popup_publicidad(page)  # no debe propagar la excepción

        assert result is False


class TestLoginRetries:
    @patch("src.scraper.login.time.sleep")
    @patch("src.scraper.login._login_once")
    def test_reintenta_hasta_max_retries_y_luego_relanza(self, mock_once, mock_sleep):
        mock_once.side_effect = RuntimeError("fallo de red")

        with pytest.raises(RuntimeError, match="fallo de red"):
            login(max_retries=3, backoff_seconds=1)

        assert mock_once.call_count == 3
        assert mock_sleep.call_count == 2  # entre intentos, no tras el último

    @patch("src.scraper.login.time.sleep")
    @patch("src.scraper.login._login_once")
    def test_no_reintenta_si_el_primer_intento_tiene_exito(self, mock_once, mock_sleep):
        mock_once.return_value = {"dashboard": "path"}

        result = login(max_retries=3)

        assert result == {"dashboard": "path"}
        assert mock_once.call_count == 1
        mock_sleep.assert_not_called()

    @patch("src.scraper.login.time.sleep")
    @patch("src.scraper.login._login_once")
    def test_exito_tras_un_fallo_no_reintenta_de_mas(self, mock_once, mock_sleep):
        mock_once.side_effect = [RuntimeError("timeout"), {"dashboard": "path"}]

        result = login(max_retries=3, backoff_seconds=1)

        assert result == {"dashboard": "path"}
        assert mock_once.call_count == 2
        assert mock_sleep.call_count == 1
