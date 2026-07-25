# src/agents — Sistema multi-agente LLM

Contiene los tres agentes que colaboran para generar cada edición del periódico.

---

## Arquitectura

```
run_newspaper.py
      │
      ▼
OrchestratorAgent  (Groq — Llama 3.3 70B)
      │
      ├──tool──► WriterAgent   (Gemini 2.5 Flash)
      │               │
      │               └─► genera JSON del periódico
      │
      └──tool──► ImageAgent    (sin LLM)
                      │
                      ├─► Bing Image Search (scraping)
                      └─► CLIP zero-shot classifier
```

---

## Ficheros

### `orchestrator_agent.py`
Coordina el pipeline completo. Usa Groq (barato y rápido) para decidir cuándo llamar al WriterAgent y al ImageAgent.

**Función principal:** `run_orchestrator(prompt, events_json, memory_context)`

- Crea el modelo Groq con `LiteLLMModel`
- Expone WriterAgent e ImageAgent como tools de Strands
- Devuelve el JSON final validado por Pydantic

### `writer_agent.py`
Genera el contenido textual del periódico en JSON.

**Función principal:** `run_writer_agent(prompt)`

- Usa Gemini 2.5 Flash para mejor calidad narrativa en español
- Invoca al agente con `structured_output_model=FinalJSON` (no el método
  `Agent.structured_output()` aparte, que se salta el bucle de tools) — así
  el agente sigue pudiendo usar sus tools y el resultado final ya viene
  validado por Pydantic sin necesidad de parsear texto.
- Hace hasta 3 reintentos si la validación falla

**Tools:**
- `generate_cards(prompt)` — llama a Gemini y devuelve las cards en bruto
- `validate_cards(cards_json)` — valida contra `SchemeValidator.FinalJSON`
- `retrieve_memory_context(query, top_k=5)` — RAG bajo demanda: memoria
  histórica adicional sobre algo puntual (una rivalidad, un jugador) más
  allá del contexto general que ya trae el prompt

### `image_agent.py`
Busca, puntúa y descarga la mejor foto para cada jugador mencionado.

**Funciones principales:**
- `search_candidate_images(jugador, equipo)` — 3 queries Bing, 8 candidatos
- `evaluate_images(candidates)` — puntuación heurística + CLIP
- `download_best_image(jugador, candidates)` — descarga el mejor

**Estrategia de puntuación:**
| Criterio | Puntos |
|----------|--------|
| URL contiene nombre del jugador | +3 |
| Extensión de imagen válida (.jpg/.png) | +2 |
| CLIP sim ≥ 0.26 (futbolista claro) | +3 |
| CLIP sim ≥ 0.22 (probable) | +2 |

> CLIP sim < 0.22 → imagen descartada (hard filter)

---

## Uso

```python
from scripts.run_newspaper import main
main()  # Pipeline completo

# O directamente:
from src.agents.orchestrator_agent import run_orchestrator
result = run_orchestrator(prompt, events_json, memory_context)
```

---

## Variables de entorno requeridas

```
GROQ_API_KEY    → para OrchestratorAgent
GEMINI_API_KEY  → para WriterAgent
```

Ver `config/.env`

---

## Issues conocidos

- **Thread safety:** llamar múltiples tools globales en paralelo puede causar conflictos con el registro global de tools de Strands ([issue #2](https://github.com/javica98/MisterFantasy_analytics/issues/2))
- **Rate limits:** Gemini 2.5 Flash tiene límite de tokens por minuto — el backfill de muchas jornadas puede saturarlo
