# Scripts — Referencia de ejecución

Todos los scripts se ejecutan desde la **raíz del proyecto**:

```bash
python scripts/<nombre>.py
```

---

## Persistencia de datos

Desde la migración a SQLite ([ADR-005](adr/005-sqlite-temporada-activa.md)), los datos de temporada (gameweek, clasificaciones, mercado, jornadas, ganancias, jugadores...) viven en `data/mister.db`, particionados por columna `temporada` (`config.yaml -> season.current` define cuál está activa). Los scripts de abajo que antes "generaban CSVs" siguen llamando a `safe_read_csv`/`safe_save_csv` (`src/utils/file_utils.py`) exactamente igual que antes — es esa capa la que ahora resuelve contra la BD, sin que el script lo note.

---

## Pipeline principal (orden de ejecución)

```
1. run_extraction.py
       ↓
2. run_preprocess.py
       ↓
3. run_newspaper.py          ← periódico IA (requiere API keys)
       ↓
4. regenerate_app_data.py    ← actualiza la web app
```

---

## Descripción detallada

### `run_extraction.py`
Parsea los HTMLs de `data/raw/` y guarda los datos en `data/mister.db` (temporada activa).

- **Input:** `data/raw/*.html` (descargados por el scraper de Playwright)
- **Output:** tablas `gameweek`, `clasificaciones`, `quiniela`, `ganancias`, `mercado`, `jornadas`, `subidasBajadas`
- **Requiere:** HTMLs actualizados en `data/raw/`

---

### `run_preprocess.py`
Limpia y normaliza los datos brutos. Aplica filtros, merges y calcula ganancias netas.

- **Input:** tabla `ganancias` (temporada activa)
- **Output:** tablas `ganancias_clean`, `ganancias_jugador`, `clausulas_acuerdos`
- **No requiere** conexión ni API keys

---

### `run_newspaper.py`
Pipeline completo de generación de periódico IA para la última jornada disponible.

1. Carga datos procesados (temporada activa)
2. Lanza `OrchestratorAgent` (Groq) que coordina:
   - `WriterAgent` (Gemini 2.5 Flash) → genera el JSON del periódico
   - `ImageAgent` (Bing + CLIP) → descarga fotos de jugadores
3. Genera imagen PNG de la portada
4. Guarda resultados en `newspaper/json/` y `newspaper/new/`

- **Requiere:** `GROQ_API_KEY` y `GEMINI_API_KEY` en `config/.env`
- **Output:** `newspaper/json/articles/`, `newspaper/json/cards/`, `newspaper/new/FECHA_jornada_news.png`

---

### `regenerate_app_data.py`
Regenera `web/data/app-data.json` a partir de los datos procesados (temporada activa) y los JSONs de periódico.

- **Input:** tablas `gameweek`, `clasificaciones`, `quiniela`, `ganancias_clean`, `jugadores` + `newspaper/json/articles/` + `newspaper/json/cards/`
- **Output:** `web/data/app-data.json` (`league.season` sale de `config.yaml -> season.current`)
- **No requiere** conexión ni API keys
- Ejecutar después de `run_newspaper.py` o cuando cambien los datos

---

### `run_dashboard.py`
Levanta un dashboard **interactivo** (Dash/Flask) en `http://127.0.0.1:8050` con estadísticas por manager. Proceso de servidor — no termina solo, hay que pararlo con Ctrl+C.

- **No requiere** API keys

### `run_monthly_dashboard.py`
Genera el informe mensual en PDF (estático, un solo proceso que termina).

- **Output:** `dashboards/reports/report_YYYY-MM-DD.pdf`
- **No requiere** API keys

---

### `rebuild_memory_embeddings.py`
Reconstruye el índice RAG de embeddings desde `newspaper/memory/memories.jsonl`.

- Ejecutar cuando se añadan nuevas memorias manualmente
- **Output:** `newspaper/memory/embeddings.npy`, `embedding_index.json`

---

### `update_memory.py`
Añade nuevas memorias al sistema RAG y regenera el índice.

---

### `manage_memories.py`
CLI de mantenimiento para `newspaper/memory/memories.jsonl`: listar (con filtros por
categoría/manager/jugador o búsqueda de texto), ver el detalle de una memoria y
borrar las incorrectas sin tener que editar el JSONL a mano.

```bash
python scripts/manage_memories.py list --category "MVP de la jornada"
python scripts/manage_memories.py show <id>
python scripts/manage_memories.py delete <id> [<id> ...] --rebuild-index
```

- **No requiere** API keys (solo `--rebuild-index` necesita `sentence-transformers`)

---

### `run_modelprocess.py`
Genera la tabla `data_model` (features para análisis predictivo, ver [Fantasy Bidding Intelligence](eda/index.md)) para la temporada activa.

---

### `run_players_db.py`
Actualiza la tabla `jugadores` (nombre, posición, club, foto) desde el HTML de Mister Fantasy (`data/raw/players_raw.html`), de forma incremental.

---

### `migrate_csv_to_sqlite.py`
Migración única: importa `archive/temporada_2025-26/data/processed/*.csv` (temporada `"2025-26"`) y `data/processed/*.csv` (temporada activa) a `data/mister.db`. Idempotente — se puede volver a ejecutar sin duplicar filas. Ya no hace falta para temporadas futuras (basta con cambiar `season.current`), solo se documenta como referencia de la migración inicial.

---

### `export_db_to_csv.py`
Exporta las tablas de `data/mister.db` a CSV, filtradas por temporada, para inspección manual o para herramientas que solo leen CSV (ej. los notebooks de [Fantasy Bidding Intelligence](eda/index.md)). No forma parte del pipeline automático ni de CI.

```bash
python scripts/export_db_to_csv.py              # temporada activa -> data/export/<temporada>/
python scripts/export_db_to_csv.py 2025-26       # temporada concreta
python scripts/export_db_to_csv.py 2025-26 out/  # directorio de salida concreto
```

---

## Scripts de diagnóstico / prueba

| Script | Descripción |
|--------|-------------|
| `run_test.py` | Test rápido del pipeline de agentes |
| `run_test_gameweek.py` | Test de extracción de gameweek |
| `test_memory_retrieval.py` | Prueba la búsqueda semántica en el RAG |
| `run_utils.py` | Utilidades varias de diagnóstico |

---

## Variables de entorno requeridas

Crear `config/.env` con:

```env
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
```
