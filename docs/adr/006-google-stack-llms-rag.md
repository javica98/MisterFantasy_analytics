# ADR-006: Todos los LLMs y el RAG usan tecnología de Google, sin migrar infraestructura

**Fecha:** 2026-09
**Estado:** Aceptado

---

## Contexto

Tras auditar la idea de migrar el proyecto a Google Cloud (ver discusión previa, no documentada como ADR por no llegar a decisión de infraestructura), se descartó mover cómputo o datos a la nube: el pipeline sigue siendo un cron batch diario/mensual sobre GitHub Actions y un mini PC propio, y no hay necesidad de escalado, concurrencia ni servicio siempre disponible que lo justifique.

Sí se decidió acotar una pieza más pequeña: estandarizar **qué proveedor de modelo** usa cada componente de IA. Hasta ahora:

- `OrchestratorAgent` usaba **Groq** (Llama 3.3 70B) — elegido en el ADR-002 por ser rápido y barato para coordinar tools.
- `WriterAgent` e `ImageAgent` ya usaban **Gemini 2.5 Flash**.
- El RAG (ADR-004) usaba `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, un modelo de la comunidad (UKPLab), no de Google.

## Decisión

Todos los LLMs y el sistema de embeddings del RAG pasan a usar tecnología de Google, **sin mover cómputo a Google Cloud** — se sigue ejecutando donde ya corría (GitHub Actions / mini PC), solo cambia qué modelo se invoca:

| Componente | Antes | Ahora |
|---|---|---|
| `OrchestratorAgent` | Groq — Llama 3.3 70B (`LiteLLMModel`) | Gemini 2.5 Flash-Lite (`strands.models.gemini.GeminiModel`) |
| `WriterAgent` | Gemini 2.5 Flash | Sin cambios |
| `ImageAgent` (agente Gemini, no el pipeline batch) | Gemini 2.5 Flash | Sin cambios |
| RAG — embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `google/embeddinggemma-300m` |

**Por qué Flash-Lite para el orquestador:** preserva el rol original de Groq (modelo rápido/barato para decidir qué tool llamar) dentro del mismo proveedor que el resto, en vez de forzar el mismo tier "Flash" que usa el `WriterAgent` para generar texto de calidad.

**Por qué EmbeddingGemma para el RAG:** es un modelo de embeddings de Google pensado para ejecutarse en local (on-device), compatible con `sentence-transformers` sin cambiar el resto de `embedding_store.py` (misma API `.encode()`, mismo índice NumPy, mismo flujo incremental del ADR-004). Mantiene los tres beneficios que el ADR-004 ya buscaba — **sin coste, offline y privado** — que sí se habrían perdido con una alternativa gestionada como Vertex AI Embeddings o Vertex AI Vector Search.

**Fuera de alcance deliberadamente:** CLIP (`clip-ViT-B-32`, clasificación de fotos, ADR-001) y Bing Image Search. Ninguno de los dos es un LLM ni parte del RAG — son parte del `ImageAgent`/pipeline de fotos, y no estaban en el alcance de esta decisión.

## Consecuencias

**Positivas:**
- Un solo proveedor de LLM (Google) para todo el proyecto — una sola API, una sola forma de facturación/cuotas, un solo SDK (`strands.models.gemini`) en vez de `strands.models.gemini` + `strands.models.litellm`.
- `requirements.txt` pierde dos dependencias (`groq`, `litellm`) que solo usaba el `OrchestratorAgent`.
- El RAG conserva exactamente las ventajas del ADR-004 (gratis, offline, privado) con pesos de Google en vez de un modelo de terceros.
- `config/.env` se simplifica: ya no hace falta `GROQ_API_KEY`.

**Negativas:**
- Se pierde la diversidad de proveedor entre orquestador y escritor que tenía el ADR-002 (Groq + Gemini) como cobertura ante una caída o cambio de precios de un proveedor concreto — ahora un incidente de Gemini afecta a los tres agentes a la vez.
- `google/embeddinggemma-300m` es un modelo con licencia Gemma en Hugging Face (gated): requiere aceptar los términos y un `HF_TOKEN` para la primera descarga, un paso operativo que el modelo anterior (totalmente abierto) no necesitaba. Mitigado: solo hace falta una vez por máquina — se cachea igual que ya se cachea CLIP — y si falla, `retrieve_relevant_memories()` cae automáticamente a búsqueda por palabras clave (no rompe el pipeline).
- No se ha podido verificar en este cambio la descarga real del modelo gated (requiere un `HF_TOKEN` válido con la licencia aceptada, no disponible en el entorno donde se hizo el cambio) ni una comparación de calidad de recuperación frente al modelo anterior — validar con `scripts/rebuild_memory_embeddings.py` en un entorno con `HF_TOKEN` antes de confiar en el RAG en producción.

## Alternativas consideradas

- **Vertex AI (API gestionada) en vez de la API directa de Gemini (AI Studio):** mismo modelo, pero añade proyecto GCP, IAM y cuotas de empresa para un proyecto que no las necesita — se descarta, ya cubierto por la auditoría de migración a Google Cloud.
- **Vertex AI Vector Search / Vertex AI Embeddings para el RAG:** gestionado, pero pensado para volúmenes (millones de vectores, baja latencia con concurrencia) muy por encima de las ~100-200 memorias de este proyecto; además pierde el "sin coste" y "offline" del ADR-004. Se descarta por sobre-ingeniería.
- **Mantener Groq como orquestador y solo migrar el RAG:** no cumple el objetivo declarado de que "todos los LLMs" usen tecnología de Google.
