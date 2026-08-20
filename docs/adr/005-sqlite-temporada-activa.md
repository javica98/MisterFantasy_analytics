# ADR-005: SQLite como fuente de verdad, particionado por `temporada`

**Fecha:** 2026-08  
**Estado:** Aceptado

---

## Contexto

Al cerrar la temporada 2025-26 hubo que archivar manualmente `data/`, `newspaper/json` y `newspaper/memory` a `archive/temporada_2025-26/` (commit `d572447`), dejando las carpetas de trabajo vacías para la temporada nueva. La razón: la columna `jornada` de los CSVs va de 1 a 38 y se reinicia cada temporada, así que sin archivar a mano la jornada 1 de la temporada nueva colisionaría con la jornada 1 de la anterior en el mismo fichero.

Ese archivado manual (`git mv` de carpetas enteras) tiene varios problemas:
- Hay que repetirlo a mano cada temporada, con riesgo de olvidarlo o hacerlo a medias.
- Ningún CSV ni ninguna parte del código modela `temporada` como un dato real — es una convención de carpetas, no un campo consultable.
- Ya generó un bug concreto: `regenerate_app_data.py` busca artículos `jornada_*_json.json`, pero `run_newspaper.py` los genera como `{fecha}_json.json` — un desajuste de nomenclatura que el archivado por carpetas no habría prevenido.
- El histórico entre temporadas no es consultable sin ir a abrir la carpeta `archive/` a mano.

## Decisión

Sustituir los CSVs de `data/processed/` por una única base de datos **SQLite** (`data/mister.db`), donde cada tabla lleva una columna `temporada` (`"2025-26"`, `"2026-27"`, ...) como parte de su clave natural junto a `jornada`/`fecha`. Varias temporadas conviven en las mismas tablas sin colisionar.

**Piezas clave:**
- `src/utils/db.py` — capa de acceso: `read_table(tabla, temporada)` / `write_table(df, tabla, temporada)`. Usa `sqlite3` (stdlib) + `pandas.to_sql`/`read_sql_query`, sin añadir SQLAlchemy ni ninguna dependencia nueva.
- `config/config.yaml` → `season.current` define la temporada activa. Cambiar de temporada es cambiar esa línea, no mover carpetas.
- `src/utils/file_utils.py::safe_read_csv/safe_save_csv` — mismo contrato de siempre (reciben/devuelven un `path` string y un DataFrame), pero si la ruta corresponde a una tabla conocida (derivada de `config.yaml -> paths.csv.*`), delegan en `db.py` en vez de tocar disco. Como todo el I/O de CSV del proyecto ya pasaba por estas dos funciones, **ningún script consumidor (`run_extraction.py`, `run_preprocess.py`, `run_modelprocess.py`, `run_dashboard.py`, `run_newspaper.py`...) necesitó cambios de código.**
- `scripts/migrate_csv_to_sqlite.py` — migración única: importa `archive/temporada_2025-26/` (`temporada="2025-26"`) y `data/processed/` (`temporada` activa) a la BD.
- `scripts/export_db_to_csv.py` — exportación puntual a CSV para inspección manual o para herramientas que sólo saben leer CSV (ej. los notebooks de `eda/`), no forma parte del pipeline automático.

**Persistencia:** el workflow de CI ([extract_trigger.yml](../../.github/workflows/extract_trigger.yml), [monthly_dashboard_trigger.yml](../../.github/workflows/monthly_dashboard_trigger.yml)) ya comiteaba `data/processed/*.csv` cada día como única forma de persistir datos entre ejecuciones efímeras. Ahora comitea `data/mister.db` en su lugar; `data/processed/` pasa a `.gitignore` como caché local opcional.

## Consecuencias

**Positivas:**
- Añadir una temporada nueva es cambiar `season.current`, no mover carpetas ni arriesgarse a olvidarlo.
- El histórico completo es consultable con SQL desde cualquier script (`SELECT * FROM gameweek WHERE temporada = '2025-26'`), sin depender de que exista una carpeta `archive/`.
- `archive/temporada_2025-26/` deja de ser necesario para temporadas futuras — se conserva como copia de seguridad de la migración inicial, no como parte del flujo.
- Cero cambios en la lógica de negocio (`src/preprocessing/`, `src/data/`, dashboards): al ser transformaciones puras `DataFrame -> DataFrame`, no les afecta de dónde vienen los datos.

**Negativas:**
- `data/mister.db` es un binario en git: los diffs dejan de ser legibles línea a línea como con los CSVs (mitigado con `export_db_to_csv.py` para quien necesite inspeccionar a mano).
- Los DataFrames que salen de la BD llevan una columna `temporada` adicional que los CSVs originales no tenían. No rompe nada (nada en el código hace comparaciones estrictas de columnas), pero es una diferencia de esquema a tener en cuenta.
- Herramientas que leen CSV directamente sin pasar por `file_utils.py` (los notebooks de `eda/`, que hacen `pd.read_csv("../data/processed/data_model.csv")`) ya no reciben datos automáticamente — hay que exportarlos primero con `python scripts/export_db_to_csv.py 2025-26`.

## Alternativas consideradas

- **Seguir archivando carpetas a mano, pero mejor organizadas** (ej. `data/seasons/<temporada>/`): resuelve la colisión de `jornada` pero no la resuelve *como dato* — seguiría sin haber un campo `temporada` consultable, y cada script tendría que saber en qué carpeta mirar.
- **PostgreSQL/MySQL gestionado**: mucho más motor del que necesita un proyecto que corre en GitHub Actions y no tiene servidor propio; SQLite es un solo fichero, cero infraestructura, y pandas lo lee/escribe igual de bien.
- **SQLAlchemy como capa ORM**: no aporta nada aquí — no hay relaciones complejas ni migraciones de esquema versionadas, y `sqlite3` + `pandas.to_sql`/`read_sql_query` cubre las dos operaciones reales (leer/escribir un DataFrame completo por temporada) sin dependencia nueva.
