# ADR-004: Sistema RAG local para memoria histórica del periódico

**Fecha:** 2026-06  
**Estado:** Aceptado

---

## Contexto

El periódico IA debe recordar eventos pasados para dar continuidad narrativa: rivalidades que se han ido creando, récords históricos, jugadores que siempre defraudan, etc. Sin memoria, cada edición es independiente y el contenido pierde profundidad.

El contexto de los LLMs tiene límite de tokens — no se pueden meter todas las ediciones anteriores en cada prompt.

## Decisión

Implementar un **sistema RAG (Retrieval-Augmented Generation) local** sin servicios externos:

**Componentes:**
- `newspaper/memory/memories.jsonl` — base de datos de memorias (una por línea)
- `newspaper/memory/embeddings.npy` — vectores NumPy de cada memoria
- `newspaper/memory/embedding_index.json` — índice id→posición en el .npy

**Modelo de embeddings:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`  
Elegido por soporte nativo en español y tamaño razonable (~120MB).

**Flujo de uso:**
1. Antes de generar el periódico, se buscan memorias relevantes con similitud coseno
2. Las top-K memorias se inyectan en el prompt como "contexto histórico"
3. Después de generar, las nuevas historias pueden añadirse como memorias para el futuro

**Optimización incremental:**  
`rebuild_embedding_index()` reutiliza vectores ya calculados para ids conocidos. Solo re-encodea memorias nuevas. Esto evita re-procesar todo el histórico cada vez.

## Consecuencias

**Positivas:**
- Sin coste: no hay llamadas a APIs de embeddings
- Privacidad: los datos de la liga nunca salen del ordenador
- Funciona offline
- El índice incremental escala bien aunque crezca el histórico

**Negativas:**
- El modelo de embeddings ocupa ~120MB y tarda ~1-2s en cargar
- La calidad de recuperación depende de que las memorias estén bien redactadas
- No hay interfaz para editar/eliminar memorias incorrectas (gestión manual del JSONL)

## Alternativas consideradas

- **ChromaDB / Qdrant local:** más features (filtros, metadata), pero más overhead para un volumen pequeño (~100-200 memorias)
- **Embeddings de OpenAI/Gemini:** coste por llamada y datos fuera del sistema
- **Sin memoria (contexto completo):** inviable cuando el histórico supere ~20 ediciones por límite de tokens
