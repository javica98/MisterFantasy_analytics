# tests — Suite de tests

Tests unitarios e de integración para todos los módulos del proyecto.

---

## Ejecutar los tests

```bash
# Todos los tests
pytest tests/ -v

# Solo unitarios (rápido, ~5s, sin red ni APIs)
pytest tests/ -v -k "not integration"

# Solo integración (más lento, lee CSVs reales)
pytest tests/ -v -k "integration"

# Un módulo concreto
pytest tests/test_generate_prompt.py -v

# Con cobertura
pytest tests/ --cov=src --cov-report=term-missing
```

---

## Estructura

```
tests/
├── conftest.py                    ← Fixtures compartidos (DataFrames de ejemplo)
├── test_config_loader.py          ← src/utils/config_loader.py
├── test_db.py                     ← src/utils/db.py
├── test_file_utils.py             ← src/utils/file_utils.py (routing CSV/BD)
├── test_generate_json.py          ← src/AI_newspaper/generate_json.py
├── test_generate_prompt.py        ← src/AI_newspaper/generate_prompt.py
├── test_scheme_validator.py       ← src/AI_newspaper/SchemeValidator.py
├── test_image_agent.py            ← src/agents/image_agent.py
├── test_embedding_store.py        ← src/memory/embedding_store.py
└── test_integration_pipeline.py  ← pipeline de punta a punta
```

---

## Descripción de cada fichero

### `conftest.py`
Fixtures de pytest disponibles en todos los tests sin importar. Incluye DataFrames de ejemplo con datos realistas de la liga.

| Fixture | Descripción |
|---------|-------------|
| `df_gameweek` | 3 jugadores, jornada 25, sin eventos especiales |
| `df_gameweek_with_events` | Con tarjeta roja, penalti parado y gol en propia |
| `df_transfers` | 3 transfers: clausula, mercado venta, mercado compra |
| `df_clasificacion` | 3 managers con puntos acumulados |
| `df_quinielas` | 3 managers con puntos de quiniela |
| `sample_events_json` | JSON de eventos completo generado desde los fixtures anteriores |

---

### `test_config_loader.py` — 9 tests
Cubre `load_config()`, `resolve_path()` y `get_base_dir()`.

Tests destacados:
- Carga correcta de `config.yaml`
- `validate_env=False` no lanza error aunque falten API keys
- `validate_env=True` lanza `EnvironmentError` con variables ausentes

---

### `test_db.py` — 13 tests
Cubre `src/utils/db.py` contra un SQLite temporal (aislado de `data/mister.db` con `monkeypatch`).

Tests destacados:
- `read_table` de una tabla inexistente devuelve `DataFrame()` vacío (misma semántica que un CSV inexistente)
- `write_table` filtra correctamente por `temporada` — escribir la 2026-27 no toca las filas de la 2025-26
- `write_table` es idempotente: reejecutarlo con el mismo DataFrame no duplica filas
- `known_tables()` deriva los nombres de `config.yaml -> paths.csv.*` y excluye `test.csv`

---

### `test_file_utils.py` — 5 tests
Cubre el enrutado de `safe_read_csv`/`safe_save_csv` (`src/utils/file_utils.py`) hacia la BD o hacia CSV en disco.

Tests destacados:
- Una ruta que corresponde a una tabla conocida se lee/escribe en la BD aunque el fichero no exista en disco
- Una ruta desconocida (ej. `test.csv`) sigue usando el CSV legacy en disco

---

### `test_generate_json.py` — 21 tests
Cubre `map_team()`, `map_position()`, `clasificacion_dict()`, `generate_json()` y `generate_json_for_jornada()`.

Tests destacados:
- IDs float de equipo (ej. `15.0`) se resuelven correctamente
- `equipoLiga=0.0` o `None` devuelve `"Sin equipo"` (bug real encontrado en datos)
- Clasificación acumulada solo hasta la jornada indicada (sin filtrar futuras)
- Jugadores sin nombre no aparecen en el JSON de output

---

### `test_generate_prompt.py` — 26 tests
Cubre todas las funciones de selección de eventos y construcción del prompt.

Tests destacados:
- `get_top_signings` ordena por `abs(ganancias)` (las compras tienen ganancias negativas)
- `get_red_cards` / `get_penalty_saves` / `get_own_goals` devuelven el primer jugador con el evento
- `build_final_prompt` incluye los bloques de eventos y el contexto de clasificación

---

### `test_scheme_validator.py` — 14 tests
Cubre `Card` y `FinalJSON` de Pydantic v2.

Tests destacados:
- `tipo` con valor no reconocido lanza `ValidationError` (gracias a `Literal`)
- `texto=[]` lanza `ValidationError` (`min_length=1`)
- `cards=[]` lanza `ValidationError` (`min_length=1`)
- Campos opcionales (`jugador`, `manager`, etc.) son `None` por defecto

---

### `test_image_agent.py` — 20 tests
Cubre el pipeline de búsqueda y descarga de imágenes, con HTTP y CLIP mockeados.

Tests destacados:
- `_expand_player_name` expande `"K. Mbappé"` → `"Mbappé"` correctamente
- `_bing_candidates` parsea el atributo `m` de `<a class="iusc">`
- `evaluate_images` puntúa correctamente con CLIP mockeado
- `download_best_image` guarda la imagen en disco sin umbral mínimo

---

### `test_embedding_store.py` — 12 tests
Cubre `rebuild_embedding_index()` y `search_similar()` con modelo de embeddings falso.

Tests destacados:
- El índice incremental reutiliza vectores ya calculados
- Búsqueda por similitud devuelve resultados ordenados por score
- El índice se reconstruye correctamente desde cero

---

### `test_integration_pipeline.py` — 22 tests
Pipeline de punta a punta, organizado en 4 tramos.

| Tramo | Tests | Descripción |
|-------|-------|-------------|
| Tramo 1 | 5 | CSVs reales cargados y parseados (sin mocks) |
| Tramo 2 | 6 | Pipeline IA con Groq/Gemini mockeados |
| Tramo 3 | 8 | Sistema RAG con modelo de embeddings falso |
| Tramo 4 | 2 | Pipeline completo encadenado + idempotencia |

> **Nota:** Los tests de Tramo 1 leen `data/processed/*.csv` directamente con `pd.read_csv` (no pasan por `safe_read_csv`/`db.py`, así que no ven los datos migrados a `data/mister.db`). Fallan si esos CSVs no existen o están vacíos — hoy es el caso de la temporada activa (`clasificaciones.csv`/`quiniela.csv` aún no se han generado esta temporada), lo que explica varios de los fallos conocidos de la sección siguiente. Para que pasen, exporta la temporada que quieras probar: `python scripts/export_db_to_csv.py 2025-26 data/processed` (o cambia `season.current` a una temporada con datos completos antes de exportar).

---

## Fallos conocidos (no relacionados con el código)

A fecha de esta migración, `pytest tests/ -q` da **202 tests, 190 pasan, 12 fallan**. Los 12 son siempre los mismos y no son un bug: dependen de que `data/processed/clasificaciones.csv`/`quiniela.csv` tengan datos, y la temporada activa (`2026-27`) todavía no ha pasado por esa parte del pipeline de extracción. Afectan a:

- `test_integration_pipeline.py` (11 tests — Tramo 1 y los que dependen de sus fixtures)
- `test_image_agent.py::test_extrae_success_true_de_la_respuesta` (no relacionado con datos de temporada ni con esta migración — ya fallaba antes, pendiente de investigar aparte)

Para verificarlos localmente con datos completos: `python scripts/export_db_to_csv.py 2025-26 data/processed` y vuelve a correr `pytest`.

---

## Warnings conocidos (no bloqueantes)

Al ejecutar la suite aparecen ~2754 warnings de:
```
DeprecationWarning: datetime.datetime.utcnow() is deprecated
```
Provienen de `src/memory/memory_builder.py` (usa `datetime.utcnow()`) y de la librería `dateutil`. **No afectan al comportamiento** — son advertencias de Python 3.12 sobre funciones que se eliminarán en versiones futuras. Pendiente de migrar a `datetime.now(datetime.UTC)`.

---

## Añadir un test nuevo

1. Crear `tests/test_mi_modulo.py`
2. Importar los fixtures que necesites (están en `conftest.py`, disponibles automáticamente)
3. Seguir la convención de clases: `class TestNombreFuncion:`
4. Ejecutar: `pytest tests/test_mi_modulo.py -v`

```python
# Ejemplo mínimo
from src.utils.team_map import map_team

class TestMapTeam:
    def test_real_madrid(self):
        assert map_team(15) == "Real Madrid"
```
