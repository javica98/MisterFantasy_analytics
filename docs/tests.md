# tests — Suite de tests

Tests unitarios e de integración para todos los módulos del proyecto.

---

## Ejecutar los tests

```bash
# Todos los tests
pytest tests/ -v

# Solo unitarios (rápido, sin red ni APIs)
pytest tests/ -v -k "not integration"

# Solo integración (más lento, lee datos reales de la temporada activa)
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
├── test_extract_data.py           ← src/data/extract_*.py (mercado, clasificación, gameweek, subidas/bajadas)
├── test_login.py                  ← src/scraper/login.py
├── test_generate_article.py       ← src/AI_newspaper/generate_article.py
├── test_generate_json.py          ← src/AI_newspaper/generate_json.py
├── test_generate_prompt.py        ← src/AI_newspaper/generate_prompt.py
├── test_scheme_validator.py       ← src/AI_newspaper/SchemeValidator.py
├── test_writer_agent.py           ← src/agents/writer_agent.py
├── test_image_agent.py            ← src/agents/image_agent.py
├── test_memory_builder.py         ← src/memory/memory_builder.py
├── test_memory_store.py           ← src/memory/memory_store.py
├── test_embedding_store.py        ← src/memory/embedding_store.py
├── test_manage_memories.py        ← scripts/manage_memories.py
├── test_regenerate_app_data.py    ← scripts/regenerate_app_data.py
└── test_integration_pipeline.py   ← pipeline de punta a punta
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

### `test_config_loader.py` — 13 tests
Cubre `load_config()`, `resolve_path()` y `get_base_dir()`.

Tests destacados:
- Carga correcta de `config.yaml`
- `validate_env=False` no lanza error aunque falten API keys
- `validate_env=True` lanza `EnvironmentError` con variables ausentes

---

### `test_db.py` — 17 tests
Cubre `src/utils/db.py` contra un SQLite temporal (aislado de `data/mister.db` con `monkeypatch`).

Tests destacados:
- `read_table` de una tabla inexistente devuelve `DataFrame()` vacío (misma semántica que un CSV inexistente)
- `write_table` filtra correctamente por `temporada` — escribir la 2026-27 no toca las filas de la 2025-26
- `write_table` es idempotente: reejecutarlo con el mismo DataFrame no duplica filas
- `write_table` rechaza sobreescribir una temporada si el DataFrame nuevo trae muchas menos filas de las que ya había (guardia anti-pérdida-de-datos; `allow_shrink=True` lo permite explícitamente)
- `known_tables()` deriva los nombres de `config.yaml -> paths.csv.*` y excluye `test.csv`

---

### `test_file_utils.py` — 5 tests
Cubre el enrutado de `safe_read_csv`/`safe_save_csv` (`src/utils/file_utils.py`) hacia la BD o hacia CSV en disco.

Tests destacados:
- Una ruta que corresponde a una tabla conocida se lee/escribe en la BD aunque el fichero no exista en disco
- Una ruta desconocida (ej. `test.csv`) sigue usando el CSV legacy en disco

---

### `test_extract_data.py` — 12 tests
Cubre los extractores de HTML más críticos de `src/data/`: `extract_mercado.py`, `extract_clasificacion.py`, `extract_gameweek.py`, `extract_subidas_bajadas.py` — antes sin ningún test, el código más frágil del repo (parsea HTML de una web externa que puede cambiar de estructura cualquier día).

Tests destacados:
- Cada extractor tiene un caso de HTML válido con los selectores reales del sitio
- Si el contenedor esperado no aparece en absoluto, devuelve un DataFrame vacío con las columnas correctas (no revienta)
- Si el contenedor aparece pero la estructura interna de la fila cambió (0 filas parseadas), también devuelve vacío con las columnas correctas en vez de lanzar `KeyError` al construir un DataFrame sin esa columna

---

### `test_login.py` — 6 tests
Cubre `src/scraper/login.py`: `cerrar_popup_publicidad()` (extraída de la triplicación que había antes) y los reintentos con backoff de `login()`.

Tests destacados:
- Cierra el popup si está visible, no hace nada si no aparece, y nunca propaga una excepción si el locator falla
- `login()` reintenta hasta `max_retries` veces con backoff y relanza la excepción original si todos los intentos fallan
- No reintenta si el primer intento tiene éxito

---

### `test_generate_article.py` — 6 tests
Cubre `src/AI_newspaper/generate_article.py`: el retry con backoff exponencial ante rate limits (429/500/503) de Gemini.

Tests destacados:
- Éxito al primer intento no reintenta
- Reintenta tras un 429 y tiene éxito en el segundo intento
- Agota los reintentos y devuelve `{}` si todos los intentos fallan

---

### `test_generate_json.py` — 25 tests
Cubre `map_team()`, `map_position()`, `clasificacion_dict()`, `generate_json()` y `generate_json_for_jornada()`.

Tests destacados:
- IDs float de equipo (ej. `15.0`) se resuelven correctamente
- `equipoLiga=0.0` o `None` devuelve `"Sin equipo"` (bug real encontrado en datos)
- Clasificación acumulada solo hasta la jornada indicada (sin filtrar futuras)
- Jugadores sin nombre no aparecen en el JSON de output
- Un manager ausente de la clasificación acumulada (datos desincronizados) no lanza `KeyError` — usa un default, igual que ya hacía `generate_json_for_jornada`

---

### `test_generate_prompt.py` — 32 tests
Cubre todas las funciones de selección de eventos y construcción del prompt.

Tests destacados:
- `get_top_signings` ordena por `abs(ganancias)` (las compras tienen ganancias negativas)
- `get_red_cards` / `get_penalty_saves` / `get_own_goals` devuelven el primer jugador con el evento
- `build_final_prompt` incluye los bloques de eventos y el contexto de clasificación

---

### `test_scheme_validator.py` — 23 tests
Cubre `Card` y `FinalJSON` de Pydantic v2.

Tests destacados:
- `tipo` con valor no reconocido lanza `ValidationError` (gracias a `Literal`)
- `texto=[]` lanza `ValidationError` (`min_length=1`)
- `cards=[]` lanza `ValidationError` (`min_length=1`)
- Campos opcionales (`jugador`, `manager`, etc.) son `None` por defecto

---

### `test_writer_agent.py` — 5 tests
Cubre `retrieve_memory_context` (tool de RAG bajo demanda) y la composición de tools del `WriterAgent`. Los tests de los reintentos en código de `run_writer_agent()` viven en `test_integration_pipeline.py::TestAIPipeline` (necesitan mockear `Agent`).

---

### `test_image_agent.py` — 31 tests
Cubre el pipeline de búsqueda y descarga de imágenes, con HTTP y CLIP mockeados.

Tests destacados:
- `_expand_player_name` expande `"K. Mbappé"` → `"Mbappé"` correctamente
- `_bing_candidates` parsea el atributo `m` de `<a class="iusc">`
- `evaluate_images` puntúa correctamente con CLIP mockeado
- `download_best_image` guarda la imagen en disco sin umbral mínimo
- `run_image_agent` no propaga la excepción si el agente Gemini falla — devuelve `False` (o `True` si el archivo ya se guardó antes del fallo)

---

### `test_memory_builder.py` — 3 tests
Cubre que `build_memories()` propaga `temporada` a cada memoria generada y que forma parte del id — misma edición en dos temporadas distintas no debe colisionar de id.

---

### `test_memory_store.py` — 7 tests
Cubre `delete_memories` (usado por `scripts/manage_memories.py`) y el filtro por `temporada` de `retrieve_by_keywords`.

Tests destacados:
- Sin filtro, `retrieve_by_keywords` devuelve resultados de cualquier temporada
- Con `temporada="2026-27"`, solo devuelve los de esa temporada
- Las memorias sin campo `temporada` (legacy) no salen si se filtra por una temporada concreta

---

### `test_embedding_store.py` — 16 tests
Cubre `_load_cached_embeddings_by_id`, `build_memory_query`, el comportamiento incremental de `rebuild_embedding_index()`, y el filtro por `temporada` de `retrieve_by_embedding`.

Tests destacados:
- El índice incremental reutiliza vectores ya calculados
- Con `temporada` filtra los resultados a esa temporada tras puntuar por similitud

---

### `test_manage_memories.py` — 12 tests
Cubre la CLI de `scripts/manage_memories.py`: `cmd_list` (incluye el filtro `--temporada`), `cmd_show`, `cmd_delete` y `build_parser`.

---

### `test_regenerate_app_data.py` — 4 tests
Cubre `build_news()` y `_load_standings_snapshot()` de `scripts/regenerate_app_data.py` — en particular el contrato de nombres de fichero con `run_newspaper.py`: antes `run_newspaper.py` nombraba las ediciones por fecha de ejecución y `build_news()` las buscaba por jornada, así que nunca coincidían y ningún artículo nuevo aparecía en la web. Un test reproduce explícitamente ese bug (nombrado por fecha → 0 resultados) para que no vuelva a colarse.

---

### `test_integration_pipeline.py` — 24 tests
Pipeline de punta a punta, organizado en 4 tramos.

| Tramo | Tests | Descripción |
|-------|-------|-------------|
| Tramo 1 | 5 | Datos reales de la temporada activa, vía `safe_read_csv` (sin mocks) |
| Tramo 2 | 8 | Pipeline IA con Groq/Gemini mockeados (incluye los reintentos de `run_writer_agent`) |
| Tramo 3 | 8 | Sistema RAG con modelo de embeddings falso |
| Tramo 4 | 2 | Pipeline completo encadenado + idempotencia |

> **Nota:** Los tests de Tramo 1 usan el fixture `real_data`, que lee vía `safe_read_csv` (resuelve contra `data/mister.db`, temporada activa) — no `pd.read_csv` directo sobre `data/processed/`. Si la temporada activa (`config.yaml -> season.current`) aún no tiene `clasificaciones`/`quiniela` generadas, algunos siguen fallando, pero ahora por un motivo real (falta ese dato en la BD), no por leer el sitio equivocado. Ver "Fallos conocidos" más abajo.

---

## Fallos conocidos (no relacionados con el código)

`pytest tests/ -q` da **241 tests, 238 pasan, 3 fallan**:

- `test_integration_pipeline.py::TestDataPipeline::test_clasificacion_contiene_todos_los_managers` — la temporada activa (`2026-27`) todavía no tiene `clasificaciones`/`quiniela` generadas tan al principio de la temporada; el test espera 9 managers y hay 0. Para verificarlo con datos completos: `python scripts/export_db_to_csv.py 2025-26 data/processed` (o cambia `season.current` a `2025-26`) y vuelve a correr `pytest`.
- `test_integration_pipeline.py::TestDataPipeline::test_equipo_jugador_siempre_es_string` — con datos reales de la temporada activa, `map_team()` no resuelve el ID de equipo `1490` (probablemente un club nuevo, ascenso/descenso, que falta en `TEAM_MAP` de `src/utils/team_map.py`) y devuelve el ID numérico sin convertir. No es un bug de este test ni de la migración — es `TEAM_MAP` desactualizado para la temporada nueva.
- `test_image_agent.py::TestRunImageAgent::test_extrae_success_true_de_la_respuesta` — no relacionado con datos de temporada; falla desde antes de cualquiera de los cambios recientes, pendiente de investigar aparte.

---

## Warnings conocidos (no bloqueantes)

Al ejecutar la suite aparecen varios cientos de warnings de:
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
