# ADR-001: Usar CLIP para clasificar fotos de jugadores

**Fecha:** 2026-06  
**Estado:** Aceptado

---

## Contexto

El `ImageAgent` busca fotos de jugadores en Bing por nombre para las portadas del periódico. El problema era que los nombres en los datos de Mister Fantasy vienen abreviados (ej. `"K. Mbappé"`) y la búsqueda devolvía imágenes irrelevantes (logos, escudos, memes). Además, se tenía un filtro de puntuación demasiado estricto que rechazaba imágenes válidas.

El sistema anterior:
- Hacía peticiones HEAD para filtrar por Content-Type → rechazaba imágenes válidas con redirects
- Tenía un umbral de puntuación mínima → sin imagen si ninguna superaba el umbral
- No tenía forma de saber si una imagen era realmente un futbolista

## Decisión

Usar **CLIP (clip-ViT-B-32)** via `sentence-transformers` como clasificador zero-shot para puntuar si una imagen contiene un futbolista de fútbol profesional.

El flujo nuevo:
1. Expandir nombre abreviado: `"K. Mbappé"` → `"Mbappé"` con regex
2. Lanzar 3 queries de Bing (nombre completo, nombre + "futbolista", nombre + equipo)
3. Recoger hasta 8 candidatos, sin filtro HEAD, con deduplicación
4. Puntuar cada imagen con CLIP: `sim(imagen, "a professional football player portrait photo")`
5. Sumar puntos CLIP (0-3) a la puntuación base de la imagen
6. Descargar siempre el mejor candidato (sin umbral mínimo)

## Consecuencias

**Positivas:**
- Fotos significativamente más relevantes en las portadas
- El modelo CLIP se cachea en memoria tras la primera carga (lazy init)
- Sin dependencia de APIs externas de pago para clasificación
- Funciona offline una vez descargado el modelo

**Negativas:**
- Primera ejecución más lenta (~2-3s de carga del modelo CLIP)
- Añade dependencia de `sentence-transformers` y `Pillow`
- El modelo ocupa ~350MB en disco

## Alternativas consideradas

- **API de Google Vision / AWS Rekognition:** coste por llamada, dependencia externa
- **Filtro por dominio:** bloquear dominios conocidos de logos → frágil y difícil de mantener
- **Revisión manual:** no escalable para múltiples jornadas
