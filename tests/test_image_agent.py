"""
Tests unitarios para src/agents/image_agent.py
Cubre: _expand_player_name, _bing_candidates (mock HTTP),
       _clip_footballer_score (mock modelo), search_candidate_images (mock)
"""
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from src.agents.image_agent import (
    _clip_footballer_score,
    _expand_player_name,
    _bing_candidates,
)


# ─────────────────────────────────────────────
# _expand_player_name
# ─────────────────────────────────────────────

class TestExpandPlayerName:
    def test_nombre_abreviado_una_inicial(self):
        assert _expand_player_name("K. Mbappé") == "Mbappé"

    def test_nombre_abreviado_dos_iniciales(self):
        assert _expand_player_name("T. Lemar") == "Lemar"

    def test_nombre_completo_sin_cambios(self):
        assert _expand_player_name("Raphinha") == "Raphinha"

    def test_nombre_mononiminco_sin_cambios(self):
        assert _expand_player_name("Gavi") == "Gavi"

    def test_inicial_compuesta(self):
        # "J.L. García" -> "García"
        assert _expand_player_name("J.L. García") == "García"

    def test_apellido_compuesto(self):
        # "C. Portu" -> "Portu"
        assert _expand_player_name("C. Portu") == "Portu"

    def test_minuscula_no_se_expande(self):
        # Nombres que empiezan por minúscula no tienen patrón de abreviación
        assert _expand_player_name("ter Stegen") == "ter Stegen"

    def test_string_vacio(self):
        assert _expand_player_name("") == ""


# ─────────────────────────────────────────────
# _bing_candidates — Playwright mockeado
# ─────────────────────────────────────────────
# _bing_candidates ya no parsea HTML en Python (ver ADR-001): abre un
# Chromium headless con Playwright y extrae los `murl` mediante JS
# (`page.evaluate`), que se ejecuta dentro del navegador. Por eso aquí
# mockeamos `playwright.sync_api.sync_playwright` y simulamos el valor
# que devolvería ese `page.evaluate` (la lista de murls ya extraída),
# en vez de servir HTML crudo a `requests.get` (que la función ya no usa).


def _mock_sync_playwright(evaluate_return=None, evaluate_side_effect=None, goto_side_effect=None):
    """
    Devuelve un patcher de `playwright.sync_api.sync_playwright` que simula:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=...)
            page.wait_for_timeout(...)
            murls = page.evaluate(js)
            browser.close()
    """
    fake_page = MagicMock()
    if goto_side_effect is not None:
        fake_page.goto.side_effect = goto_side_effect
    if evaluate_side_effect is not None:
        fake_page.evaluate.side_effect = evaluate_side_effect
    else:
        fake_page.evaluate.return_value = evaluate_return or []

    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page

    fake_p = MagicMock()
    fake_p.chromium.launch.return_value = fake_browser

    fake_context_manager = MagicMock()
    fake_context_manager.__enter__.return_value = fake_p
    fake_context_manager.__exit__.return_value = False

    return patch(
        "playwright.sync_api.sync_playwright",
        return_value=fake_context_manager,
    ), fake_page


class TestBingCandidates:
    def test_extrae_murls_correctamente(self):
        """page.evaluate ya devuelve los murls extraídos por el JS del navegador."""
        patcher, _ = _mock_sync_playwright(evaluate_return=[
            "https://img1.example.com/mbappe.jpg",
            "https://img2.example.com/real_madrid.png",
        ])
        with patcher:
            result = _bing_candidates("Mbappé Real Madrid futbolista", max_results=10)

        assert "https://img1.example.com/mbappe.jpg" in result
        assert "https://img2.example.com/real_madrid.png" in result

    def test_filtra_urls_con_extension_no_valida(self):
        """Los murls con extensión no-imagen se descartan vía _is_bad_url, aunque el JS los devuelva."""
        patcher, _ = _mock_sync_playwright(evaluate_return=[
            "https://img1.example.com/mbappe.jpg",
            "https://img3.example.com/photo.gif",
        ])
        with patcher:
            result = _bing_candidates("query", max_results=10)

        assert "https://img1.example.com/mbappe.jpg" in result
        assert not any(u.endswith(".gif") for u in result)

    def test_max_results_se_incluye_en_el_js_evaluado(self):
        """
        max_results se pasa embebido en el string JS de page.evaluate
        (el corte real de resultados ocurre en el navegador, no en Python).
        """
        patcher, fake_page = _mock_sync_playwright(evaluate_return=["https://img1.example.com/a.jpg"])
        with patcher:
            _bing_candidates("query", max_results=3)

        js_arg = fake_page.evaluate.call_args[0][0]
        assert "urls.length >= 3" in js_arg

    def test_evaluate_devuelve_lista_vacia(self):
        patcher, _ = _mock_sync_playwright(evaluate_return=[])
        with patcher:
            result = _bing_candidates("query", max_results=5)

        assert result == []

    def test_error_de_navegador_devuelve_lista_vacia(self):
        """Si Playwright falla (timeout, navegador no disponible, etc.), se captura y devuelve []."""
        patcher, _ = _mock_sync_playwright(goto_side_effect=Exception("timeout"))
        with patcher:
            result = _bing_candidates("query", max_results=5)

        assert result == []


# ─────────────────────────────────────────────
# _clip_footballer_score — modelo mockeado
# ─────────────────────────────────────────────

def _make_image(w=400, h=600, color=(100, 150, 200)):
    return Image.new("RGB", (w, h), color)


def _mock_clip_model(sim_value: float):
    """Crea un mock del modelo CLIP que devuelve siempre el mismo vector."""
    mock_model = MagicMock()
    # Vectores unitarios que producirán la similitud deseada
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([sim_value, np.sqrt(max(0, 1 - sim_value**2)), 0.0], dtype=np.float32)
    mock_model.encode.side_effect = [v1, v2, v2]  # img, pos, neg
    return mock_model


class TestClipFootballerScore:
    def test_similitud_alta_da_3_puntos(self):
        img = _make_image()
        with patch("src.agents.image_agent._get_clip_model") as mock_get:
            mock_model = MagicMock()
            # Simulamos vectores con similitud coseno ~0.28
            vec_high = np.array([1.0, 0.0], dtype=np.float32)
            mock_model.encode.return_value = vec_high
            mock_get.return_value = mock_model

            with patch("src.agents.image_agent.np.dot", return_value=0.28), \
                 patch("src.agents.image_agent.np.linalg") as mock_la:
                mock_la.norm.return_value = 1.0
                pts, reason = _clip_footballer_score(img)

        assert pts == 3.0
        assert "futbolista" in reason.lower()

    def test_similitud_baja_da_0_puntos(self):
        img = _make_image()
        with patch("src.agents.image_agent._get_clip_model") as mock_get:
            mock_model = MagicMock()
            vec = np.array([1.0, 0.0], dtype=np.float32)
            mock_model.encode.return_value = vec
            mock_get.return_value = mock_model

            with patch("src.agents.image_agent.np.dot", return_value=0.10), \
                 patch("src.agents.image_agent.np.linalg") as mock_la:
                mock_la.norm.return_value = 1.0
                pts, reason = _clip_footballer_score(img)

        assert pts == 0.0

    def test_error_en_clip_devuelve_0_sin_lanzar(self):
        img = _make_image()
        with patch("src.agents.image_agent._get_clip_model", side_effect=Exception("CLIP error")):
            pts, reason = _clip_footballer_score(img)

        assert pts == 0.0
        assert "error" in reason.lower()

    def test_imagen_rgb_no_lanza_excepcion(self):
        """CLIP debe convertir la imagen a RGB internamente sin fallar."""
        img = _make_image().convert("RGBA")  # RGBA -> debe convertirse a RGB
        with patch("src.agents.image_agent._get_clip_model") as mock_get:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.ones(512, dtype=np.float32)
            mock_get.return_value = mock_model
            # No debe lanzar excepción
            pts, reason = _clip_footballer_score(img)
        assert isinstance(pts, float)


# ─────────────────────────────────────────────
# Integración ligera: search_candidate_images tool
# ─────────────────────────────────────────────

class TestSearchCandidateImagesTool:
    def test_devuelve_json_valido(self):
        from src.agents.image_agent import search_candidate_images

        with patch("src.agents.image_agent._bing_candidates", return_value=[
            "https://example.com/foto1.jpg",
            "https://example.com/foto2.jpg",
        ]):
            raw = search_candidate_images("Mbappé", "Real Madrid")

        data = json.loads(raw)
        assert "candidates" in data
        assert "jugador" in data
        assert "equipo" in data
        assert data["jugador"] == "Mbappé"
        assert data["equipo"] == "Real Madrid"

    def test_deduplicacion_de_urls(self):
        from src.agents.image_agent import search_candidate_images

        duplicadas = ["https://example.com/foto.jpg"] * 5
        with patch("src.agents.image_agent._bing_candidates", return_value=duplicadas):
            raw = search_candidate_images("Raphinha", "FC Barcelona")

        data = json.loads(raw)
        assert len(data["candidates"]) == 1  # deduplicado

    def test_excluye_extensiones_no_imagen(self):
        from src.agents.image_agent import search_candidate_images

        urls = [
            "https://example.com/foto.jpg",
            "https://example.com/video.mp4",
            "https://example.com/icon.svg",
            "https://example.com/anim.gif",
        ]
        with patch("src.agents.image_agent._bing_candidates", return_value=urls):
            raw = search_candidate_images("Lemar", "Atlético de Madrid")

        data = json.loads(raw)
        for url in data["candidates"]:
            assert not url.endswith((".mp4", ".svg", ".gif"))

    def test_expande_nombre_abreviado_en_query(self):
        """Si el jugador tiene nombre abreviado, la query debe usar el apellido."""
        from src.agents.image_agent import search_candidate_images

        queries_usadas = []

        def fake_bing(query, max_results):
            queries_usadas.append(query)
            return []

        with patch("src.agents.image_agent._bing_candidates", side_effect=fake_bing):
            search_candidate_images("K. Mbappé", "Real Madrid")

        # Al menos una query debe contener "Mbappé" (sin la inicial)
        assert any("Mbappé" in q for q in queries_usadas)


# ─────────────────────────────────────────────
# run_image_agent — camino real usado por el Orchestrator (Agent/Gemini mockeado)
# ─────────────────────────────────────────────

class TestRunImageAgent:
    def test_extrae_success_true_de_la_respuesta(self, tmp_path):
        from src.agents.image_agent import run_image_agent

        save_path = str(tmp_path / "Portada.jpg")
        fake_response = f'He terminado. {{"success": true, "path": "{save_path}", "score": 9.5}}'

        with patch("src.agents.image_agent.Agent") as mock_agent_cls:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda self: fake_response)
            mock_agent_cls.return_value = mock_instance

            result = run_image_agent("Mbappé", "Real Madrid", save_path)

        assert result is True

    def test_extrae_success_false_aunque_el_archivo_exista(self, tmp_path):
        """El JSON de la respuesta manda sobre la existencia del archivo en disco."""
        from src.agents.image_agent import run_image_agent

        save_path = tmp_path / "Portada.jpg"
        save_path.write_bytes(b"fake-image-bytes")
        fake_response = '{"success": false, "error": "sin candidatas validas"}'

        with patch("src.agents.image_agent.Agent") as mock_agent_cls:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda self: fake_response)
            mock_agent_cls.return_value = mock_instance

            result = run_image_agent("Mbappé", "Real Madrid", str(save_path))

        assert result is False

    def test_sin_json_en_la_respuesta_cae_a_comprobar_el_archivo(self, tmp_path):
        from src.agents.image_agent import run_image_agent

        save_path = tmp_path / "Portada.jpg"
        save_path.write_bytes(b"fake-image-bytes")

        with patch("src.agents.image_agent.Agent") as mock_agent_cls:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda self: "Foto descargada correctamente.")
            mock_agent_cls.return_value = mock_instance

            result = run_image_agent("Mbappé", "Real Madrid", str(save_path))

        assert result is True

    def test_sin_json_ni_archivo_devuelve_false(self, tmp_path):
        from src.agents.image_agent import run_image_agent

        save_path = tmp_path / "no_existe.jpg"

        with patch("src.agents.image_agent.Agent") as mock_agent_cls:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda self: "No se encontraron fotos.")
            mock_agent_cls.return_value = mock_instance

            result = run_image_agent("Mbappé", "Real Madrid", str(save_path))

        assert result is False


# ─────────────────────────────────────────────
# run_image_pipeline — flujo sin LLM (search -> evaluate -> download)
# ─────────────────────────────────────────────

class TestRunImagePipeline:
    def test_camino_feliz_encadena_las_tres_funciones(self, tmp_path):
        from src.agents.image_agent import run_image_pipeline

        save_path = str(tmp_path / "Portada.jpg")
        candidates_json = json.dumps({
            "candidates": ["https://example.com/a.jpg"], "jugador": "Mbappé", "equipo": "Real Madrid",
        })
        evaluation_json = json.dumps({"best_url": "https://example.com/a.jpg", "best_score": 9.0, "scores": []})
        download_json = json.dumps({"success": True, "path": save_path, "score": 9.0})

        with patch("src.agents.image_agent._search_candidates", return_value=candidates_json) as mock_search, \
             patch("src.agents.image_agent._evaluate_candidates", return_value=evaluation_json) as mock_eval, \
             patch("src.agents.image_agent._download_best", return_value=download_json) as mock_download:

            result = run_image_pipeline("Mbappé", "Real Madrid", save_path)

        assert result is True
        mock_search.assert_called_once_with("Mbappé", "Real Madrid")
        mock_eval.assert_called_once_with(candidates_json)
        mock_download.assert_called_once_with(evaluation_json, save_path)

    def test_download_fallido_devuelve_false(self, tmp_path):
        from src.agents.image_agent import run_image_pipeline

        save_path = str(tmp_path / "no_existe.jpg")

        with patch("src.agents.image_agent._search_candidates", return_value=json.dumps({"candidates": []})), \
             patch("src.agents.image_agent._evaluate_candidates",
                   return_value=json.dumps({"best_url": None, "best_score": 0, "scores": []})), \
             patch("src.agents.image_agent._download_best",
                   return_value=json.dumps({"success": False, "error": "No hay URL válida para descargar"})):

            result = run_image_pipeline("Mbappé", "Real Madrid", save_path)

        assert result is False

    def test_excepcion_con_archivo_previo_devuelve_true(self, tmp_path):
        """Si algo revienta a mitad del pipeline, se recurre a comprobar si el archivo ya existe."""
        from src.agents.image_agent import run_image_pipeline

        save_path = tmp_path / "Portada.jpg"
        save_path.write_bytes(b"fake-image-bytes")

        with patch("src.agents.image_agent._search_candidates", side_effect=Exception("red caida")):
            result = run_image_pipeline("Mbappé", "Real Madrid", str(save_path))

        assert result is True

    def test_excepcion_sin_archivo_previo_devuelve_false(self, tmp_path):
        from src.agents.image_agent import run_image_pipeline

        save_path = tmp_path / "no_existe.jpg"

        with patch("src.agents.image_agent._search_candidates", side_effect=Exception("red caida")):
            result = run_image_pipeline("Mbappé", "Real Madrid", str(save_path))

        assert result is False
