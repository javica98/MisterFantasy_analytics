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

El dict devuelto contiene `cfg["paths"]`, `cfg["scraper"]`, `cfg["logging"]` y `cfg["env"]`.

### `data_utils.py`
Helpers para manipulación de DataFrames: filtros de fechas, normalización de columnas.

### `file_utils.py`
Helpers de I/O: leer/escribir JSON con encoding UTF-8, crear directorios.

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
