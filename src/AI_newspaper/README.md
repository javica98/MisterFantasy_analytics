# src/AI_newspaper — Pipeline de contenido del periódico

Módulos que transforman los datos de la liga en el contenido de cada edición del periódico.

---

## Flujo interno

```
CSVs procesados
      │
      ▼
generate_json.py        ← convierte DataFrames en eventos estructurados
      │
      ▼
generate_prompt.py      ← selecciona eventos relevantes y construye el prompt
      │
      ▼
[WriterAgent llama a Gemini]
      │
      ▼
SchemeValidator.py      ← valida que el JSON cumpla el schema
      │
      ▼
generate_article.py     ← (opcional) genera texto narrativo largo
      │
      ▼
generate_pdf.py         ← renderiza la imagen PNG de la portada
```

---

## Ficheros

### `generate_json.py`
Transforma los DataFrames de pandas en el diccionario `events_json` que consume el agente.

**Funciones clave:**
- `generate_json(jornada, df_transfers, df_gameweek, df_clasificacion, df_quinielas)` → dict
- `generate_json_for_jornada(...)` → versión con fechas explícitas para backfill
- `clasificacion_dict(df)` → `{manager: {puntos, posicion}}`

Los IDs numéricos de equipo se resuelven a nombres usando `src.utils.team_map`.

### `generate_prompt.py`
Selecciona los eventos más relevantes y construye el prompt para el LLM.

**Funciones clave:**
- `get_top_signings(transfers, top_n=3)` → fichajes más caros (por `abs(ganancias)`)
- `get_top_sale(transfers)` → mayor venta en mercado libre
- `get_mvps(gameweek, top_n=3)` → jugadores con más puntos
- `get_worst_player(gameweek)` → jugador con menos puntos
- `get_red_cards(gameweek)` → primer jugador con tarjeta roja
- `get_penalty_saves(gameweek)` → portero que paró penalti
- `get_own_goals(gameweek)` → jugador con gol en propia
- `generate_prompts(events_json)` → construye bloques de eventos
- `build_final_prompt(bloques, events_json, memory_context)` → prompt final

### `SchemeValidator.py`
Modelos Pydantic v2 para validar el JSON generado por el LLM.

```python
TIPOS_CARD = Literal["clasificacion", "rumor", "Fichaje destacado", ...]

class Card(BaseModel):
    tipo: TIPOS_CARD
    titulo: str
    subtitulo: str
    texto: List[str]   # min 1 elemento
    jugador: Optional[str]
    manager: Optional[str]
    puntos: Optional[float]
    dinero: Optional[float]
    equipo: Optional[str]

class FinalJSON(BaseModel):
    cards: List[Card]  # min 1 card
```

Ver [ADR-003](../../docs/adr/003-pydantic-v2-schema-validacion.md) para el razonamiento.

### `generate_pdf.py`
Renderiza las cards del JSON en una imagen PNG estilo portada de periódico.

### `generate_article.py`
Genera un artículo narrativo largo (texto libre) a partir de los eventos. Opcional.

---

## Tipos de card disponibles

| tipo | Descripción |
|------|-------------|
| `clasificacion` | Resumen de la clasificación general |
| `rumor` | Rumor gracioso (inventado por el LLM) |
| `Fichaje destacado` | Compra más cara de la semana |
| `Venta récord` | Mayor venta en mercado libre |
| `MVP de la jornada` | Jugador con más puntos |
| `Peor actuación de la jornada` | Jugador con menos puntos |
| `Expulsión` | Jugador con tarjeta roja |
| `Héroe bajo palos` | Portero que paró un penalti |
| `Gol en propia` | Jugador que marcó en propia puerta |
