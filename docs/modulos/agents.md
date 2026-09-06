# src/agents — Sistema multi-agente LLM

Contiene los agentes que colaboran para generar cada edición del periódico.

---

## Arquitectura

```
run_newspaper.py
      │
      ├──► _fetch_portada_image() × 2, en paralelo (ThreadPoolExecutor)
      │         │
      │         ├─► cache por jugador+equipo (newspaper/photos/cache/)
      │         └─► run_image_pipeline()   (sin LLM: Bing + CLIP)
      │
      ▼
OrchestratorAgent  (Groq — Llama 3.3 70B)
      │
      └──tool──► WriterAgent   (Gemini 2.5 Flash)
                      │
                      └─► genera JSON del periódico
```

Las dos fotos de portada ya no son un tool call que Groq deba decidir
invocar: se buscan en paralelo con Python plano (`_fetch_portada_image`,
sin pasar por Gemini) antes de llamar al agente de texto, y se cachean por
jugador+equipo para no repetir la búsqueda en Bing si el mismo MVP/fichaje
vuelve a salir en portada otro día. El `OrchestratorAgent` (Groq) ahora
coordina únicamente al `WriterAgent`.

---

## Ficheros

### `orchestrator_agent.py`
Coordina el texto (vía Groq) y dispara la búsqueda de fotos en paralelo.

**Función principal:** `run_orchestrator(prompt, portada_fichajes, portada_jornada, path_fichajes, path_jornada)`

- `_fetch_portada_image()` busca cada foto con `run_image_pipeline` (sin
  LLM), lanzadas en paralelo con `ThreadPoolExecutor`, reutilizando una
  copia cacheada si el mismo jugador+equipo ya salió en portada antes
- Crea el modelo Groq con `LiteLLMModel`
- Expone solo `run_writer` como tool de Strands
- Si Groq no reproduce el JSON de cards en su respuesta, hace fallback
  directo a `run_writer_agent(prompt)` (las fotos ya están listas de antes,
  no se repite esa parte)
- Devuelve el JSON final validado por Pydantic

### `writer_agent.py`
Genera el contenido textual del periódico en JSON.

**Función principal:** `run_writer_agent(prompt)`

- Usa Gemini 2.5 Flash para mejor calidad narrativa en español
- Invoca al agente con `structured_output_model=FinalJSON` (no el método
  `Agent.structured_output()` aparte, que se salta el bucle de tools) — así
  el agente sigue pudiendo usar sus tools y el resultado final ya viene
  validado por Pydantic sin necesidad de parsear texto.
- Reintenta la invocación completa hasta 3 veces con backoff (5s, 10s, ...)
  si el agente falla o no produce cards válidas — es un reintento real en
  código Python, no solo la instrucción "máximo 2 reintentos" del prompt

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
- `run_image_pipeline(jugador, equipo, save_path)` — encadena las tres
  anteriores en Python puro, sin LLM. Es la que usa `orchestrator_agent.py`
  para las dos portadas en paralelo.
- `run_image_agent(jugador, equipo, save_path)` — la misma búsqueda pero
  orquestada por un agente Gemini con las tres funciones como tools. Nunca
  propaga excepciones (devuelve `False` si Gemini falla), para no tirar el
  resto del pipeline por un fallo que solo afecta a la imagen.

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

cards = run_orchestrator(
    prompt=prompt_txt,
    portada_fichajes={"jugador": "K. Mbappé", "equipo": "Real Madrid"},
    portada_jornada={"jugador": "Raphinha", "equipo": "FC Barcelona"},
    path_fichajes="newspaper/photos/Portada_Fichajes.jpg",
    path_jornada="newspaper/photos/Portada_Jornada.jpg",
)
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

- **Rate limits:** Gemini 2.5 Flash tiene límite de tokens por minuto — el backfill de muchas jornadas puede saturarlo

Resuelto: el conflicto de thread-safety por llamar tools globales de Strands
en paralelo ([issue #2](https://github.com/javica98/MisterFantasy_analytics/issues/2))
ya no aplica — las fotos de portada dejaron de ser tool calls y se buscan
con `ThreadPoolExecutor` en Python plano, fuera del bucle de Strands.
