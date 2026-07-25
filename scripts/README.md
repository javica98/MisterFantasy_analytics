# Scripts — Referencia de ejecución

Todos los scripts se ejecutan desde la **raíz del proyecto**:

```bash
python scripts/<nombre>.py
```

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
Parsea los HTMLs de `data/raw/` y genera los CSVs en `data/processed/`.

- **Input:** `data/raw/*.html` (descargados manualmente de Mister Fantasy)
- **Output:** `data/processed/gameweek.csv`, `clasificaciones.csv`, `quiniela.csv`, `ganancias.csv`, etc.
- **Requiere:** HTMLs actualizados en `data/raw/`

---

### `run_preprocess.py`
Limpia y normaliza los CSVs brutos. Aplica filtros, merges y calcula ganancias netas.

- **Input:** CSVs de `data/processed/` (brutos)
- **Output:** `ganancias_clean.csv`, `ganancias_jugador.csv`, `clausulas_acuerdos.csv`
- **No requiere** conexión ni API keys

---

### `run_newspaper.py`
Pipeline completo de generación de periódico IA para la última jornada disponible.

1. Carga CSVs procesados
2. Lanza `OrchestratorAgent` (Groq) que coordina:
   - `WriterAgent` (Gemini 2.5 Flash) → genera el JSON del periódico
   - `ImageAgent` (Bing + CLIP) → descarga fotos de jugadores
3. Genera imagen PNG de la portada
4. Guarda resultados en `newspaper/json/` y `newspaper/new/`

- **Requiere:** `GROQ_API_KEY` y `GEMINI_API_KEY` en `config/.env`
- **Output:** `newspaper/json/articles/`, `newspaper/json/cards/`, `newspaper/new/FECHA_jornada_news.png`

---

### `regenerate_app_data.py`
Regenera `web/data/app-data.json` a partir de los CSVs procesados y los JSONs de periódico.

- **Input:** CSVs procesados + `newspaper/json/articles/` + `newspaper/json/cards/`
- **Output:** `web/data/app-data.json`
- **No requiere** conexión ni API keys
- Ejecutar después de `run_newspaper.py` o cuando cambien los CSVs

---

### `run_dashboard.py` / `run_monthly_dashboard.py`
Genera PDFs de estadísticas por manager.

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
Genera `data/processed/data_model.csv` con features para análisis predictivo.

---

### `run_players_db.py`
Actualiza `data/processed/jugadores.csv` con jugadores y sus fotos desde el HTML de Mister Fantasy.

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
