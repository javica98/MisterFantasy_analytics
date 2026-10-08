# Roadmap — Calidad de los datos diarios (temporada 2026-27)

Auditoría del 07/10/2026 sobre `data/mister.db`, el historial de git (una versión de la BD por día) y una exploración de solo lectura de Mister con sesión real (`scripts/explore_mister*.py`).

## Diagnóstico

| Tabla | Estado | Causa raíz |
|---|---|---|
| `gameweek` | Faltan **112 filas** (J1, J3–J7). Ejemplo: la J7 tiene 36 filas de 77 y 5 partidos de 10 | 1) El scraper solo lee la jornada que muestra la web. Al día siguiente de acabar ya se ve la siguiente, y se pierden los partidos del último día. 2) `merge_gameweek` usa `keep="first"`: no recoge las correcciones de puntos (3 detectadas). |
| `clasificaciones` | Faltan J1, J4 y J5. La J3 tiene puntos desfasados (50/49 en la web y 51/48 en la BD) | 1) Solo se lee la jornada *seleccionada*. Con el calendario desordenado (J6 antes que J4), J4 y J5 nunca estuvieron seleccionadas. 2) J1: el merge falló con el CSV vacío del 17/08 y guardó vacío. 3) Las correcciones posteriores de Mister no se reflejan. |
| `mercado`, `subidasBajadas`, `jornadas`, `ganancias` | Faltan los días 17–20/08 | Se perdieron en la migración de CSV a SQLite del 20/08. Los días 17, 18 y 20 están en git (`af1cd55`). El 19 no existe: esa ejecución se canceló. |
| `ganancias` | 199 filas duplicadas | Marcadores `marks/start_mercado` sin datos. Son inocuos, pero hacen ruido. |
| `jugadores`, `data_model` | Vacías en 2026-27 | No las rellena el workflow diario. |
| Workflow | Todas las ejecuciones en verde | No hay ninguna validación de datos y el issue automático nunca salta. |

**Aplazados (confirmado):** en la J6, Levante–Athletic sigue pendiente (21/10/2026). Mister marca la J6 como `ongoing` del 03/09 al 21/10. Con el código actual ese partido se perdería casi seguro.

### Qué descubrimos en Mister

- `POST /ajax/sw/gameweek` con `post=gameweek&id=<id_gameweek>` devuelve JSON con:
  - el **calendario completo**: todas las jornadas con `status` (`finished`, `ongoing` o `unstarted`) y `firstMatchDate`/`lastMatchDate`;
  - los 10 partidos de la jornada, cada uno con `status` (`played` o `fixture`), su fecha real (`date.ts`), goles e ids de los equipos.
- Al pulsar el botón `.gameweek-selector-inline button[data-id=<id>]` en `feed#gameweek`, se renderiza la jornada completa. El extractor actual funciona sin cambios sobre ese HTML y saca los 10 partidos y los 9 managers.
- `standings?gw=<id_gameweek>` da la clasificación de cualquier jornada pasada.
- Ids de 2026-27: J1=3968, J2=4043, J3=4044 … J7=4048, J8=4049. Se leen siempre del JSON y nunca se fijan en el código.

---

## Fase 0 — Recuperar lo perdido (una sola vez)

| # | Tarea | Fuente | Resultado |
|---|---|---|---|
| 0.1 | Rehacer `gameweek` J1–J7 | Botón por jornada en `feed#gameweek`, con `Date` = fecha real del partido | +112 filas y 3 correcciones de puntos |
| 0.2 | Rehacer `clasificaciones` J1–J7 | `standings?gw=<id>` | J1, J4 y J5 nuevas; J3 corregida |
| 0.3 | Importar los días 17, 18 y 20/08 | CSVs del commit `af1cd55`, con dedupe contra la BD | Huecos de `mercado`, `subidasBajadas`, `jornadas` y `ganancias` cubiertos |
| 0.4 | Documentar el 19/08 como día perdido | — | Que la validación no avise siempre por ese hueco |

> **Estado:** 0.1 y 0.2 los hace solo el scraper de la Fase 1 en su primera ejecución. Para 0.3 está `scripts/backfill_from_git.py af1cd55 2026-08-17 2026-08-20 [--apply]`. Es idempotente; sin `--apply` solo muestra los cambios. Añade 69 filas de `mercado`, 1.479 de `subidasBajadas` y 6 de `jornadas`. En `ganancias` no faltaba ningún traspaso: los 35 de esos días tenían fecha 21/08 y se les pone la real. 0.4: el 19/08 está en `validation.dias_perdidos` de `config.yaml`.

## Fase 1 — Scraper robusto (el cambio de fondo)

> **Estado (07/10/2026):** puntos 1–5 implementados y probados (tests unitarios, simulación sobre una copia de la BD y scrape en vivo de J1–J7). El punto 6 pasa a la Fase 3. La primera ejecución del workflow descargará J1–J7 completas porque `partidos` está vacía, y con eso queda hecho también el backfill de gameweek y clasificaciones de la Fase 0 (0.1 y 0.2).

1. **Nuevas tablas `calendario` y `partidos`.** Se rellenan desde `/ajax/sw/gameweek`, con estado, fecha real y goles de cada partido. Son la referencia para saber qué *debería* haber.
2. **Revisar varias jornadas cada día ("ventana activa").** Cada ejecución procesa:
   - toda jornada `ongoing`;
   - toda jornada `finished` cuyo `lastMatchDate` sea de hace menos de 7 días, para recoger correcciones de puntos;
   - toda jornada con algún partido `played` que aún no esté completo en la BD. Esto cubre los aplazados aunque se jueguen un mes después.

   Para cada una: `gameweek` (botón `data-id`) y `clasificaciones` (`standings?gw=`).
3. **Upsert en lugar de `keep="first"`.** Se reemplazan las filas de cada `(jornada, partido)` releído, para que entren las correcciones de puntos. En `clasificaciones` ya se reemplaza por jornada; solo cambia que se leen más jornadas.
4. **`Date` del gameweek = fecha real del partido** (de `partidos`), no la del día del scrape.
5. **Merges a prueba de tabla vacía.** Si la tabla anterior está vacía o no tiene columnas, se usa la nueva tal cual. Sin esto, cualquier error vuelve a vaciar la tabla, que es justo lo que se cargó la J1.
6. **`ganancias`:** descartar los marcadores `marks/start_mercado` en la extracción o en el preprocesado.
7. **Más adelante (opcional):** pedir `/ajax/sw/gameweek` directamente con `page.request.post` desde el contexto ya autenticado, sin clics. Primero hay que comprobar si el JSON incluye los jugadores de todos los managers o solo los tuyos; si es así, se podría quitar el parseo de HTML.

## Fase 2 — Validación automática en el workflow

> **Estado:** implementada en `scripts/validate_data.py` y añadida al workflow diario como paso `Validate data`, después del commit. Usa una copia de la BD tomada antes de extraer para detectar tablas que pierden filas. Los aplazados salen como aviso, no como error.

`scripts/validate_data.py` se ejecuta tras el preprocesado y antes del commit. Si encuentra un error, falla el job y salta el issue que ya existe.

| Check | Error si… |
|---|---|
| Continuidad diaria | Falta algún día en `mercado`, `subidasBajadas` o `jornadas` (salvo los días documentados como perdidos) |
| Frescura | El último dato tiene más de 36 h |
| Gameweek vs calendario | En una jornada, los partidos con datos ≠ los partidos `played` en `partidos`. Los aplazados (`fixture`) **no** cuentan como error |
| Managers por partido jugado | Hay menos managers que la jornada anterior sin explicación |
| Clasificaciones | Una jornada `finished` no tiene sus 9 managers |
| Duplicados | Hay duplicados por clave en cualquier tabla (sin contar los marcadores) |
| Merge vacío | Una tabla tiene menos filas que antes del run |

También genera un resumen en `$GITHUB_STEP_SUMMARY` para ver el estado de cada día sin abrir logs.

## Fase 3 — Operativa y limpieza

- **Tests con fixtures:** guardar HTML/JSON reales de Mister (anonimizados) en `tests/fixtures/` y probar los extractores y el upsert con ellos.
- **Comentario del cron:** `0 7 * * *` son las 07:00 UTC, no las 9:00. En la práctica GitHub lo lanza entre las 12 y las 14 UTC. Con la ventana activa la hora deja de importar.
- **`jugadores` y `data_model`:** decidir si entran en el workflow diario o semanal (`run_players_db.py`, `run_modelprocess.py`).
- **Cerrar el issue #7** ("Workflow failure: Daily Data Extraction", de agosto), que sigue abierto.
- **Scripts de exploración:** guardar `scripts/explore_mister*.py` como herramientas de diagnóstico. Sus salidas van a `data/raw/`, que git ignora.

## Orden propuesto

1. **Fase 1, puntos 1–5.** Es lo más urgente: la J8 empieza el 09/10 y Levante–Athletic de la J6 se juega el 21/10.
2. **Fase 0.** Usa el código de la Fase 1, así que el backfill sale casi gratis.
3. **Fase 2.**
4. **Fase 3.**

## Fase 4 — Más datos y menos dependencia del HTML (07/10/2026)

| # | Mejora | Estado |
|---|---|---|
| 4.1 | `scraped_at` (UTC) en `mercado`, `subidasBajadas` y `jornadas`. El dedupe la ignora, así que repetir un run el mismo día no duplica filas | ✅ |
| 4.2 | El feed (`ganancias`) sale del JSON de `/ajax/feed`: fecha real de cada tarjeta (`date` y `created` con hora), `aciertos` y `points` rellenos. Mismo orden e `idTransfer` que el HTML (verificado en vivo: 396/396 filas). Si al JSON le falta algún traspaso del HTML, se usa el HTML | ✅ |
| 4.3 | `partidos_stats`: unas 48 métricas por partido (posesión, xG, tiros…) | ✅ |
| 4.4 | `once_ideal`: mejor once de cada jornada | ✅ |
| 4.5 | `alineaciones_probables`: 11 por equipo y partido, con el flag `confirmado` | ✅ |
| 4.6 | Pasar `mercado` y `quiniela` a JSON | Pendiente. Hay que explorar sus endpoints |

`write_table` añade solas las columnas nuevas (`ALTER TABLE`), así que ampliar el esquema no requiere migraciones.
