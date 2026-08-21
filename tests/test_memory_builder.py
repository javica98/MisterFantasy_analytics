"""
Tests para src/memory/memory_builder.py — en particular que `temporada` se
propaga a cada memoria generada y forma parte del id (hallazgo IA-02).
"""
from src.memory.memory_builder import build_memories


def _events_json():
    return {
        "fecha_inicio": "2026-08-17",
        "fecha_fin": "2026-08-20",
        "transfers": [{
            "fecha": "2026-08-18", "subtype": "mercado", "equipo": "Dani",
            "jugador": "Mbappé", "compra_venta": "compra",
            "equipo_jugador": "Real Madrid", "ganancias": -30.0,
            "clasificacion_manager_general": {"puntos": 100, "posicion": 1},
            "clasificacion_manager_jornada": {"puntos": 10, "posicion": 1},
        }],
        "gameweek": [{
            "fecha": "2026-08-18", "jornada": 3, "manager": "Dani",
            "jugador": "Mbappé", "equipo_jugador": "Real Madrid", "puntos": 18,
            "posicion": "Delantero", "goles": 2, "asistencias": 0,
            "roja": 0, "gol_propia": 0, "penalti_parado": 0, "penalti_fallado": 0,
            "clasificacion_manager_general": {"puntos": 100, "posicion": 1},
            "clasificacion_manager_jornada": {"puntos": 10, "posicion": 1},
        }],
        "clasificacion": {
            "general": {"Dani": {"puntos": 100, "posicion": 1}, "Maldinillo": {"puntos": 90, "posicion": 2}},
            "jornada": {"Dani": {"puntos": 10, "posicion": 1}},
        },
        "quinielas": {"general": {}, "jornada": {}},
    }


class TestBuildMemoriesTemporada:
    def test_temporada_se_propaga_a_todas_las_memorias(self):
        memories = build_memories(_events_json(), temporada="2026-27")

        assert len(memories) > 0
        assert all(m["temporada"] == "2026-27" for m in memories)

    def test_sin_temporada_queda_none(self):
        memories = build_memories(_events_json())

        assert all(m["temporada"] is None for m in memories)

    def test_misma_edicion_en_dos_temporadas_da_ids_distintos(self):
        memorias_2025 = build_memories(_events_json(), temporada="2025-26")
        memorias_2026 = build_memories(_events_json(), temporada="2026-27")

        ids_2025 = {m["id"] for m in memorias_2025}
        ids_2026 = {m["id"] for m in memorias_2026}

        # Mismos datos de entrada, distinta temporada -> ids no deben colisionar
        assert ids_2025.isdisjoint(ids_2026)
