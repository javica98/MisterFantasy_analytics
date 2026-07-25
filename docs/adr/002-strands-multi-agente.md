# ADR-002: Arquitectura multi-agente con Strands Framework

**Fecha:** 2026-06  
**Estado:** Aceptado

---

## Contexto

Generar una portada de periódico completa requiere tareas heterogéneas:
- Escribir texto creativo y sensacionalista (requiere un LLM de alta calidad)
- Buscar y descargar fotos de jugadores (requiere scraping + clasificación ML)
- Coordinar ambas tareas y manejar errores

El reto era ejecutar estas tareas con modelos distintos, de forma orquestada, sin crear acoplamiento fuerte entre ellas.

## Decisión

Usar **Strands Agent Framework** con 3 agentes especializados:

| Agente | Modelo | Responsabilidad |
|--------|--------|-----------------|
| `OrchestratorAgent` | Groq Llama 3.3 70B | Coordina, decide qué herramientas llamar |
| `WriterAgent` | Gemini 2.5 Flash | Genera el JSON del periódico |
| `ImageAgent` | — (sin LLM) | Busca y descarga fotos con CLIP |

El `OrchestratorAgent` expone `WriterAgent` e `ImageAgent` como **tools** de Strands. Cada tool es una closure que encapsula su propio estado (prompt, cache de resultados).

**Por qué Groq para orquestación y Gemini para escritura:**
- Groq (Llama 3.3 70B) es rápido y barato → ideal para decisiones de coordinación
- Gemini 2.5 Flash tiene mejor calidad narrativa en español → ideal para generar el texto del periódico

## Consecuencias

**Positivas:**
- El orchestrator no necesita saber los detalles de cada agente
- Fácil añadir nuevos agentes como tools
- Modelos independientes: se puede cambiar Gemini por otro sin tocar el orquestador
- Strands maneja el bucle de llamadas a tools automáticamente

**Negativas:**
- Strands es un framework relativamente nuevo con documentación limitada
- Hay un problema conocido con threads cuando se llaman múltiples tools globales en paralelo (ver [issue #2](https://github.com/javica98/MisterFantasy_analytics/issues/2))
- Los errores de API (rate limits) del writer llegan envueltos en el output del orchestrator

## Alternativas consideradas

- **LangChain / LangGraph:** más maduro pero más verboso y con más overhead
- **Un solo LLM:** no permite especializar el modelo por tarea ni controlar costes
- **Llamadas directas sin framework:** más simple pero sin gestión automática del bucle de tools
