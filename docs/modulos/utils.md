# src/utils — Utilidades compartidas

Módulos de uso general importados por el resto del proyecto.

---

## Ficheros

### `team_map.py`
Fuente única de verdad para mapeos de IDs numéricos a nombres legibles.

```python
from src.utils.team_map import map_team, map_position, TEAM_MAP, TEAM_POSICION

map_team(15)      # → "Real Madrid"
map_team(15.0)    # → "Real Madrid"  (los CSVs dan floats)
map_team(None)    # → "Sin equipo"
map_team(0)       # → "Sin equipo"   (jugadores sin equipo en liga)

map_position(1)   # → "Portero"
map_position(4)   # → "Delantero"
```

**Equipos mapeados:** Real Madrid, FC Barcelona, Atlético de Madrid, Sevilla FC, Real Betis, Real Sociedad, Villarreal CF, Athletic Club, Valencia CF, CA Osasuna, RC Celta, Rayo Vallecano, Deportivo Alavés, RCD Espanyol, Getafe CF, Girona FC, RCD Mallorca, Real Oviedo, Elche CF, Levante UD

### `config_loader.py`
Carga `config/config.yaml` y opcionalmente las variables de entorno de `config/.env`.

```python
from src.utils.config_loader import load_config

cfg = load_config()                     # carga config + env
cfg = load_config(validate_env=False)   # solo config, sin exigir API keys
```

El dict devuelto contiene `cfg["paths"]`, `cfg["scraper"]`, `cfg["logging"]`, `cfg["env"]`, `cfg["data"]` (incluye `db_path`) y `cfg["season"]` (incluye `current`, la temporada activa).

### `data_utils.py`
Helpers para manipulación de DataFrames: filtros de fechas, normalización de columnas.

### `file_utils.py`
Helpers de I/O seguro (no lanzan excepción si falta el archivo/tabla, devuelven vacío y loggean): `safe_read_html`, `safe_read_json`/`safe_save_json`, `safe_read_text`/`safe_save_text`, `safe_read_png`/`safe_save_png`, y `safe_read_csv`/`safe_save_csv`.

Estas dos últimas son el único punto de entrada de datos tabulares de todo el proyecto. Si la ruta pasada corresponde a una tabla conocida de `config.yaml -> paths.csv.*`, delegan en `src/utils/db.py` (leen/escriben en `data/mister.db`, filtrado por la temporada activa); si no, caen al CSV en disco de siempre. El resto del código (`run_extraction.py`, `run_preprocess.py`, dashboards...) no necesita saber cuál de los dos casos aplica.

```python
from src.utils.file_utils import safe_read_csv, safe_save_csv

df = safe_read_csv("data/processed/gameweek.csv")   # -> lee tabla "gameweek" de la BD, temporada activa
safe_save_csv(df, "data/processed/gameweek.csv")    # -> sobreescribe esa temporada en la BD
```

### `db.py`
Capa de acceso a `data/mister.db` (SQLite, particionado por columna `temporada`). Ver [ADR-005](../adr/005-sqlite-temporada-activa.md).

```python
from src.utils import db

db.get_active_season()                              # -> "2026-27" (config.yaml -> season.current)
db.read_table("gameweek", temporada="2025-26")       # -> DataFrame de esa temporada (vacío si no existe)
db.write_table(df, "gameweek", temporada="2026-27")  # -> sobreescribe esa temporada (DELETE + INSERT)
```

Usa `sqlite3` (stdlib) + `pandas.to_sql`/`read_sql_query`, sin dependencias nuevas. `known_tables()` deriva los nombres de tabla válidos de `config.yaml -> paths.csv.*` (excluye `test.csv`, que sigue siendo un CSV legacy en disco).

### `photo_utils.py`
Utilidades para redimensionar y convertir imágenes (usadas en `generate_pdf.py`).

### `bootstrap.py`
Inicialización del entorno: configura logging, carga config, añade `src/` al `sys.path`.

### `text_cleaning.py`
Limpieza de strings: normalización de tildes, mayúsculas, caracteres especiales.

---

## Convención de importación

```python
# Siempre importar desde src.utils, nunca rutas relativas
from src.utils.team_map import map_team
from src.utils.config_loader import load_config
```
