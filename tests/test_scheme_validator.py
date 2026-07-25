"""
Tests unitarios para src/AI_newspaper/SchemeValidator.py
Cubre: Card, FinalJSON — validación Pydantic
"""
import pytest
from pydantic import ValidationError

from src.AI_newspaper.SchemeValidator import Card, FinalJSON


# ─────────────────────────────────────────────
# Card
# ─────────────────────────────────────────────

class TestCard:
    def test_card_minima_valida(self):
        card = Card(
            tipo="clasificacion",
            titulo="Título de prueba",
            subtitulo="Subtítulo",
            texto=["Frase uno", "Frase dos"],
        )
        assert card.tipo == "clasificacion"
        assert card.jugador is None
        assert card.manager is None

    def test_card_completa_valida(self):
        card = Card(
            tipo="MVP de la jornada",
            jugador="Mbappé",
            manager="Maldinillo",
            puntos=18.0,
            dinero=None,
            equipo="Real Madrid",
            titulo="¡El mejor!",
            subtitulo="Goleador de la jornada",
            texto=["Mbappé lo dio todo.", "Dos goles y una asistencia."],
        )
        assert card.jugador == "Mbappé"
        assert card.puntos == 18.0

    def test_texto_vacio_falla(self):
        with pytest.raises(ValidationError):
            Card(
                tipo="clasificacion",
                titulo="T",
                subtitulo="S",
                texto=[],  # min_items=1
            )

    def test_titulo_requerido(self):
        with pytest.raises(ValidationError):
            Card(
                tipo="clasificacion",
                subtitulo="S",
                texto=["Frase"],
            )

    def test_subtitulo_requerido(self):
        with pytest.raises(ValidationError):
            Card(
                tipo="clasificacion",
                titulo="T",
                texto=["Frase"],
            )

    def test_tipo_requerido(self):
        with pytest.raises(ValidationError):
            Card(
                titulo="T",
                subtitulo="S",
                texto=["Frase"],
            )

    def test_puntos_puede_ser_entero_o_float(self):
        card_int = Card(tipo="rumor", titulo="T", subtitulo="S", texto=["F"], puntos=10)
        card_float = Card(tipo="rumor", titulo="T", subtitulo="S", texto=["F"], puntos=10.5)
        assert card_int.puntos == 10.0
        assert card_float.puntos == 10.5

    def test_campos_opcionales_por_defecto_none(self):
        card = Card(tipo="rumor", titulo="T", subtitulo="S", texto=["F"])
        assert card.jugador is None
        assert card.manager is None
        assert card.puntos is None
        assert card.dinero is None
        assert card.equipo is None

    def test_tipo_invalido_falla(self):
        with pytest.raises(ValidationError):
            Card(tipo="tipo_inventado", titulo="T", subtitulo="S", texto=["F"])

    # ── Coherencia semántica tipo <-> campos requeridos (ADR-003) ──────────

    def test_mvp_sin_jugador_falla(self):
        with pytest.raises(ValidationError):
            Card(tipo="MVP de la jornada", puntos=18.0, titulo="T", subtitulo="S", texto=["F"])

    def test_mvp_sin_puntos_falla(self):
        with pytest.raises(ValidationError):
            Card(tipo="MVP de la jornada", jugador="Mbappé", titulo="T", subtitulo="S", texto=["F"])

    def test_fichaje_sin_dinero_falla(self):
        with pytest.raises(ValidationError):
            Card(tipo="Fichaje destacado", jugador="Raphinha", titulo="T", subtitulo="S", texto=["F"])

    def test_fichaje_sin_jugador_falla(self):
        with pytest.raises(ValidationError):
            Card(tipo="Fichaje destacado", dinero=56.0, titulo="T", subtitulo="S", texto=["F"])

    def test_venta_record_requiere_jugador_y_dinero(self):
        with pytest.raises(ValidationError):
            Card(tipo="Venta récord", titulo="T", subtitulo="S", texto=["F"])

    def test_expulsion_requiere_jugador_y_puntos(self):
        with pytest.raises(ValidationError):
            Card(tipo="Expulsión", jugador="ter Stegen", titulo="T", subtitulo="S", texto=["F"])

    def test_clasificacion_no_requiere_jugador_ni_puntos(self):
        """clasificacion y rumor no están ligados a un jugador concreto."""
        card = Card(tipo="clasificacion", titulo="T", subtitulo="S", texto=["F"])
        assert card.jugador is None

    def test_rumor_no_requiere_jugador_ni_puntos(self):
        card = Card(tipo="rumor", titulo="T", subtitulo="S", texto=["F"])
        assert card.jugador is None

    def test_mvp_con_todos_los_campos_es_valida(self):
        card = Card(
            tipo="MVP de la jornada", jugador="Mbappé", manager="Maldinillo",
            puntos=18.0, equipo="Real Madrid", titulo="T", subtitulo="S", texto=["F"],
        )
        assert card.puntos == 18.0


# ─────────────────────────────────────────────
# FinalJSON
# ─────────────────────────────────────────────

class TestFinalJSON:
    def _make_card(self, tipo="clasificacion"):
        return {
            "tipo": tipo,
            "titulo": "Título",
            "subtitulo": "Subtítulo",
            "texto": ["Frase uno"],
        }

    def test_finaljson_valido(self):
        fj = FinalJSON(cards=[self._make_card()])
        assert len(fj.cards) == 1

    def test_cards_vacias_falla(self):
        with pytest.raises(ValidationError):
            FinalJSON(cards=[])  # min_items=1

    def test_multiples_cards(self):
        mvp_card = self._make_card("MVP de la jornada")
        mvp_card.update({"jugador": "Mbappé", "puntos": 18.0})

        fj = FinalJSON(cards=[
            self._make_card("clasificacion"),
            self._make_card("rumor"),
            mvp_card,
        ])
        assert len(fj.cards) == 3

    def test_card_invalida_dentro_de_finaljson_falla(self):
        with pytest.raises(ValidationError):
            FinalJSON(cards=[{
                "tipo": "clasificacion",
                "titulo": "T",
                # falta subtitulo y texto
            }])

    def test_parse_desde_dict(self):
        data = {
            "cards": [
                {
                    "tipo": "clasificacion",
                    "jugador": None,
                    "manager": None,
                    "puntos": None,
                    "dinero": None,
                    "equipo": None,
                    "titulo": "¡La liga arde!",
                    "subtitulo": "Nada está decidido",
                    "texto": ["Frase 1", "Frase 2"],
                }
            ]
        }
        fj = FinalJSON(**data)
        assert fj.cards[0].titulo == "¡La liga arde!"
