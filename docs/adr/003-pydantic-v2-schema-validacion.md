# ADR-003: Validación de output LLM con Pydantic v2 + Literal types

**Fecha:** 2026-06  
**Estado:** Aceptado

---

## Contexto

El `WriterAgent` genera un JSON con el contenido del periódico. Los LLMs a veces devuelven JSON malformado, campos faltantes, o valores inesperados en campos enumerados (como el campo `tipo` de cada card).

Sin validación, un JSON inválido causa errores silenciosos en la web app o genera portadas con contenido incorrecto.

## Decisión

Validar el output del LLM con **Pydantic v2** usando un schema estricto en `src/AI_newspaper/SchemeValidator.py`.

Puntos clave:

**1. `Literal` types para el campo `tipo`:**
```python
TIPOS_CARD = Literal[
    "clasificacion", "rumor", "Fichaje destacado", "Venta récord",
    "MVP de la jornada", "Peor actuación de la jornada",
    "Expulsión", "Héroe bajo palos", "Gol en propia",
]
```
Si el LLM devuelve un tipo no reconocido (ej. `"mvp"` en minúsculas), Pydantic lanza `ValidationError` inmediatamente.

**2. `min_length=1` en listas (Pydantic v2):**
```python
texto: List[str] = Field(..., min_length=1)
cards: List[Card] = Field(..., min_length=1)
```
Migrado desde `min_items` (Pydantic v1) para eliminar deprecation warnings.

**3. El prompt también refuerza el schema:**
El prompt incluye los tipos exactos permitidos y ejemplos de JSON válido. La validación Pydantic es la red de seguridad final.

## Consecuencias

**Positivas:**
- Errores del LLM se detectan antes de llegar a la web app
- Los tipos permitidos están en un solo sitio (`TIPOS_CARD`) — el prompt y el validador son consistentes
- Fácil añadir nuevos tipos de card: añadir al `Literal` y al prompt

**Negativas:**
- Si el LLM genera un tipo válido pero semánticamente incorrecto, Pydantic no lo detecta
- La validación no reintenta automáticamente; si falla, el script lanza error (hay que reintentar manualmente o añadir retry logic)

## Alternativas consideradas

- **JSON Schema + jsonschema:** más verboso, sin integración directa con el resto del código Python
- **Sin validación:** más rápido de implementar, pero genera bugs silenciosos difíciles de depurar
- **Structured outputs de la API:** Gemini/Groq soportan structured outputs, pero introduce acoplamiento con el proveedor específico
