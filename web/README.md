# web — Web App estática

Aplicación web de estadísticas de la Sotano League. Es completamente estática: HTML + CSS + JS sin servidor, sin build step, sin dependencias npm.

---

## Abrir en el navegador

Simplemente abre `index.html` directamente, o sirve la carpeta con cualquier servidor HTTP:

```bash
# Python (desde la raíz del proyecto)
python -m http.server 8080
# → abrir http://localhost:8080/web/

# VS Code: extensión Live Server → botón "Go Live"
```

---

## Estructura

```
web/
├── index.html      ← estructura HTML de la app
├── styles.css      ← estilos (variables CSS, layout, componentes)
├── app.js          ← lógica de la app (carga datos, renderiza vistas)
├── covers/         ← portadas WebP (las genera regenerate_app_data.py)
│   ├── default.webp
│   └── {temporada}/jornada_N.webp, jornada_N-large.webp
└── data/
    └── app-data.json   ← datos generados por regenerate_app_data.py
```

---

## Despliegue en AI Center

La web se sirve 24/7 como contenedor Docker (`misterfantasy-web`, nginx) dentro
del `docker-compose.yml` global de AI Center, en `ai-center-network`.

```bash
# Desde C:\AI_CENTER
docker compose build misterfantasy-web
docker compose up -d misterfantasy-web
```

- `Dockerfile.web` (raíz del proyecto) copia `web/` y `assets/` — el resto del
  repo (datos, credenciales, scripts, `newspaper/`, `archive/`) queda fuera de
  la imagen (`.dockerignore`). Las portadas del carrusel van como miniaturas
  en `web/covers/`, así que no hace falta nada de `newspaper/`.
- `docker/nginx.web.conf` sirve `web/index.html` en `/` porque la app usa rutas
  absolutas (`/web/...`, `/assets/web/...`). También activa gzip, caché
  (`no-cache` + ETag para HTML y datos, 1 día para estáticos) y las cabeceras de
  seguridad de `docker/security-headers.inc`. Ojo con la CSP: no metas
  `onclick=`/`onerror=` inline en el HTML que genera `app.js` porque los
  bloquea; para el respaldo de imágenes usa `data-fallback`.
- Puerto configurable con `MISTERFANTASY_WEB_PORT` en `C:\AI_CENTER\.env`
  (por defecto `8090`). Acceso: `http://localhost:8090/` o vía Tailscale
  `http://100.120.149.53:8090/`.
- Para exponerla con subdominio propio, añadir un Proxy Host en Nginx Proxy
  Manager (`http://100.120.149.53:81`) apuntando a `misterfantasy-web:80`.
- El workflow diario (`extract_trigger.yml`) regenera `app-data.json` y las
  miniaturas, las comitea y, al terminar, dispara `deploy_web.yml`
  (`workflow_run`), que reconstruye la imagen. Si lo regeneras a mano, el push
  a `main` también redespliega.

## Actualizar los datos

Los datos se regeneran con:

```bash
python scripts/regenerate_app_data.py
```

Esto sobreescribe `web/data/app-data.json` y crea las miniaturas que falten en `web/covers/`. No hay que tocar nada más — la app carga el JSON dinámicamente al abrirla. La pastilla de la cabecera muestra la fecha de `generatedAt` y se pone en ámbar si tiene más de 3 días.

---

## Estructura de `app-data.json`

Este es el contrato de datos entre el pipeline Python y la web app.

```jsonc
{
  "generatedAt": "2026-06-09T21:26:09",  // ISO datetime de última generación

  "league": { ... },      // Stats globales de la liga
  "managers": [ ... ],    // Array de 9 managers con sus stats
  "news": [ ... ],        // Periódicos generados (más reciente primero)
  "playersMap": { ... },  // { "NombreJugador": "url_foto" }
  "seasons": ["2025-26", "2026-27"],   // ascendente; la última es la temporada en curso
  "activeSeason": "2026-27",           // season.current de config.yaml al generar
  "defaultCover": "/web/covers/default.webp",
  "managersBySeason": { "2026-27": [ ... ] },  // mismo formato que managers[]
  "newsBySeason":     { "2026-27": [ ... ] }   // mismo formato que news[]
}
```

### `league`

```jsonc
{
  "name": "Sotano League",
  "season": "2026-27",
  "dateRange": "2026-08-16 · 2026-09-20",
  "lastRound": 7,                         // última jornada con datos
  "standings": [                          // Clasificación general
    { "rank": 1, "manager": "Dani", "points": 1450, "prevRank": 2 }  // prevRank: puesto en la captura anterior (flechas ▲▼)
  ],
  "poolStandings": [ ... ],               // Clasificación quinielas
  "managerOfMonth": {                     // Manager con más puntos en la ÚLTIMA JORNADA (la web lo titula así)
    "name": "Maldinillo",
    "subtitle": "...",
    "description": "..."
  },
  "playerOfMonth": {                      // Jugador con más puntos en la última jornada
    "name": "Mbappé", "team": "Real Madrid",  // team ya traducido con map_team()
    "manager": "Maldinillo", "points": 18,
    "description": "..."
  },
  "latestHeadline": { "type": "...", "title": "...", "subtitle": "...", "text": [] },  // primera card del periódico más reciente (claves en inglés, como news[].cards)
  "mostExpensiveBuy": {                   // Compra más cara de mercado libre
    "player": "Mbappé", "manager": "Maldinillo", "amount": 131.4
  },
  "mostExpensiveClause": { ... },         // Clausulazo más caro
  "mostClausesGiven":    { "manager": "...", "count": 3 },   // Más clausulazos SUFRIDOS (ventas por cláusula)
  "mostClausesReceived": { "manager": "...", "count": 5 },   // Más clausulazos REALIZADOS (compras por cláusula)
  // Ojo: los nombres son contraintuitivos. Antes de oct-2026 la web los mostraba cruzados.
  "topClauses": [                         // Top 5 clausulazos (de→a, importe)
    { "player": "...", "from": "...", "to": "...", "amount": 56.0 }
  ],
  "topTransfers": [                       // Top 5 compras de mercado libre
    { "player": "...", "manager": "...", "amount": 20.0 }
  ]
}
```

### `managers[]`

Cada objeto en el array representa un manager:

```jsonc
{
  "name": "Maldinillo",
  "position": 1,              // Posición en clasificación general
  "totalPoints": 1450,
  "weekPoints": 72,           // Puntos de la última jornada
  "average": 68.4,            // Media de puntos por jornada
  "stdDev": 12.3,             // Desviación estándar
  "goals": 187,               // Goles totales de sus jugadores
  "assists": 134,
  "redCards": 8,
  "bestPlayer": {             // Mejor jugador esta temporada
    "name": "Mbappé", "team": "Real Madrid",
    "position": "Delantero", "points": 210
  },
  "worstPlayer": { ... },     // Jugador con menos puntos
  "bestPlayerHistoric": { ... },  // hoy idéntico a bestPlayer (la web solo muestra uno)
  "transferCount": 12,        // Número de compras realizadas
  "marketSpend": 450.5,       // Dinero total gastado en compras (millones)
  "market": {
    "mercado": 5,             // Compras en mercado libre
    "clausulas": 4,           // Clausulazos ejecutados
    "acuerdos": 3             // Acuerdos entre managers
  },
  "form": [72, 65, 80, 58, 71, 90, 68, 72],  // Puntos últimas 8 jornadas
  "seasonForm": [55, 61, null, 70],          // posición i = jornada i+1; null = jornada sin datos en la BD
  "comparison": {}            // Reservado para comparativas futuras
}
```

### `news[]`

Array de periódicos generados, ordenado del más reciente al más antiguo:

```jsonc
[
  {
    "date": "J17",
    "cover": "/web/covers/2026-27/jornada_17.webp",        // miniatura 240px; null si no hay portada (la web usa defaultCover)
    "coverLarge": "/web/covers/2026-27/jornada_17-large.webp",  // 900px, para la portada protagonista y el visor
    "title": "¡La liga explota!",
    "subtitle": "Nada está decidido",
    "summary": "Frase resumen...",
    "cards": [                  // Cards del periódico, traducidas a claves en inglés
      {
        "type": "clasificacion",
        "title": "¡La liga explota!",
        "subtitle": "Nada está decidido",
        "text": ["Frase 1", "Frase 2", "Frase 3"],
        "jugador": null, "manager": null, "puntos": null, "dinero": null
      }
    ],
    "standingsAtIssue": [ { "rank": 1, "manager": "Dani", "points": 120 } ]
  }
]
```

### `playersMap`

Diccionario plano `{ nombre: url_foto }` para mostrar fotos de jugadores:

```jsonc
{
  "K. Mbappé": "https://cdn.mister.com/players/...",
  "Vinicius Jr.": "https://cdn.mister.com/players/...",
  ...
}
```

Contiene ~557 jugadores de la tabla `jugadores` de `data/mister.db` (todas las temporadas, quedándose con la fila más reciente de cada nombre). Esa tabla solo la rellena `scripts/run_players_db.py`, que no corre en el workflow diario: los fichajes nuevos de una temporada salen con iniciales hasta que se vuelva a ejecutar.
