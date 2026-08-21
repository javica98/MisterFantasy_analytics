"""
Tests unitarios para src/AI_newspaper/generate_article.py
Cubre: retry con backoff exponencial ante rate limits (429) de Gemini.
"""
from unittest.mock import MagicMock, patch

from google.genai import errors as genai_errors

from src.AI_newspaper.generate_article import generate_articles


def _api_error(code: int) -> genai_errors.APIError:
    return genai_errors.APIError(
        code=code,
        response_json={"error": {"message": "boom", "status": "ERROR"}},
    )


class TestGenerateArticlesRetry:
    def test_exito_al_primer_intento_no_reintenta(self):
        fake_response = MagicMock(parsed={"cards": [{"tipo": "clasificacion"}]})

        with patch(
            "src.AI_newspaper.generate_article.client.models.generate_content",
            return_value=fake_response,
        ) as mock_call, patch("src.AI_newspaper.generate_article.time.sleep") as mock_sleep:
            result = generate_articles("prompt de prueba")

        assert result == {"cards": [{"tipo": "clasificacion"}]}
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()

    def test_reintenta_tras_429_y_luego_tiene_exito(self):
        fake_response = MagicMock(parsed={"cards": [{"tipo": "rumor"}]})

        with patch(
            "src.AI_newspaper.generate_article.client.models.generate_content",
            side_effect=[_api_error(429), fake_response],
        ) as mock_call, patch("src.AI_newspaper.generate_article.time.sleep") as mock_sleep:
            result = generate_articles("prompt de prueba")

        assert result == {"cards": [{"tipo": "rumor"}]}
        assert mock_call.call_count == 2
        mock_sleep.assert_called_once_with(5)  # backoff base en el primer reintento

    def test_backoff_exponencial_entre_reintentos(self):
        with patch(
            "src.AI_newspaper.generate_article.client.models.generate_content",
            side_effect=[_api_error(429), _api_error(503), _api_error(429)],
        ), patch("src.AI_newspaper.generate_article.time.sleep") as mock_sleep:
            result = generate_articles("prompt de prueba")

        assert result == {}
        # 3 intentos -> 2 esperas, con backoff exponencial: 5s, 10s
        assert [call.args[0] for call in mock_sleep.call_args_list] == [5, 10]

    def test_agota_reintentos_y_devuelve_dict_vacio(self):
        with patch(
            "src.AI_newspaper.generate_article.client.models.generate_content",
            side_effect=_api_error(429),
        ) as mock_call, patch("src.AI_newspaper.generate_article.time.sleep"):
            result = generate_articles("prompt de prueba")

        assert result == {}
        assert mock_call.call_count == 3  # _MAX_ATTEMPTS

    def test_error_no_reintentable_no_espera(self):
        """Un error de cliente no listado (ej. 400 Bad Request) no dispara reintentos."""
        with patch(
            "src.AI_newspaper.generate_article.client.models.generate_content",
            side_effect=_api_error(400),
        ) as mock_call, patch("src.AI_newspaper.generate_article.time.sleep") as mock_sleep:
            result = generate_articles("prompt de prueba")

        assert result == {}
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()

    def test_excepcion_generica_no_reintenta(self):
        """Errores que no son de la API de Gemini (red, etc.) se comportan como antes: sin retry."""
        with patch(
            "src.AI_newspaper.generate_article.client.models.generate_content",
            side_effect=ConnectionError("red caida"),
        ) as mock_call, patch("src.AI_newspaper.generate_article.time.sleep") as mock_sleep:
            result = generate_articles("prompt de prueba")

        assert result == {}
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()
