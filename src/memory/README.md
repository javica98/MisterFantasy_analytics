# src/memory — Sistema RAG de memoria histórica

Proporciona memoria a largo plazo al periódico IA. Almacena eventos relevantes de ediciones pasadas y los recupera por similitud semántica para enriquecer el contexto del LLM.

Ver [ADR-004](../../docs/adr/004-rag-memoria-periodico.md) para la decisión de arquitectura.

---

## Componentes

```
newspaper/memory/
├── memories.jsonl        ← base de datos (una memoria por línea)
├── embeddings.npy        ← vectores NumPy [N x D]
└── embedding_index.json  ← { "id": índice_en_npy }
```

---

## Ficheros

### `embedding_store.py`
Gestiona el índice de vectores NumPy para búsqueda por similitud coseno.

**Funciones clave:**
- `rebuild_embedding_index(...)` — reconstruye el índice desde `memories.jsonl`. Incremental: reutiliza vectores ya calculados para IDs conocidos.
- `search_similar(query, top_k, ...)` — devuelve las K memorias más similares a la query (similitud coseno).

**Modelo:** `paraphrase-multilingual-MiniLM-L12-v2` (soporta español de forma nativa)

### `memory_store.py`
CRUD básico sobre `memories.jsonl`.

**Funciones clave:**
- `read_memories(path)` → lista de dicts
- `append_memory(memory, path)` → añade una memoria al final del fichero
- `memory_exists(id, path)` → comprueba si ya existe una memoria con ese ID

### `memory_builder.py`
Construye memorias estructuradas a partir del output del periódico.

---

## Formato de una memoria

```json
{
  "id": "jornada_17_mvp_mbappe",
  "jornada": 17,
  "tipo": "MVP de la jornada",
  "texto": "Mbappé firmó 18 puntos llevando a Maldinillo a lo más alto de la clasificación.",
  "jugador": "Mbappé",
  "manager": "Maldinillo",
  "fecha": "2026-03-04"
}
```

---

## Uso

```python
from src.memory.embedding_store import search_similar, rebuild_embedding_index

# Buscar memorias relevantes antes de generar el periódico
memorias = search_similar("Mbappé gran actuación", top_k=3)
memory_context = "\n".join(m["texto"] for m in memorias)

# Reconstruir índice tras añadir nuevas memorias
rebuild_embedding_index()
```

---

## Mantenimiento

- El índice se reconstruye automáticamente en cada ejecución de `run_newspaper.py`
- Para añadir memorias manualmente: editar `memories.jsonl` y ejecutar `scripts/rebuild_memory_embeddings.py`
- Para listar, inspeccionar o borrar memorias incorrectas: `python scripts/manage_memories.py list|show|delete` (ver `scripts/README.md`)
