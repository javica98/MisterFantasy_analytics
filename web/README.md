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
  repo (datos, credenciales, scripts) queda fuera de la imagen (`.dockerignore`).
- `docker/nginx.web.conf` sirve `web/index.html` en `/` porque la app usa rutas
  absolutas (`/web/...`, `/assets/web/...`).
- Puerto configurable con `MISTERFANTASY_WEB_PORT` en `C:\AI_CENTER\.env`
  (por defecto `8090`). Acceso: `http://localhost:8090/` o vía Tailscale
  `http://100.120.149.53:8090/`.
- Para exponerla con subdominio propio, añadir un Proxy Host en Nginx Proxy
  Manager (`http://100.120.149.53:81`) apuntando a `misterfantasy-web:80`.
- Al regenerar `app-data.json` (`python scripts/regenerate_app_data.py`), hay
  que reconstruir la imagen para que el contenedor sirva los datos nuevos.

## Actualizar los datos

Los datos se regeneran con:

```bash
python scripts/regenerate_app_data.py
```

Esto sobreescribe `web/data/app-data.json`. No hay que tocar nada más — la app carga el JSON dinámicamente al abrirla.

---

## Estructura de `app-data.json`

Este es el contrato de datos entre el pipeline Python y la web app.

```jsonc
{
  "generatedAt": "2026-06-09T21:26:09",  // ISO datetime de última generación

  "league": { ... },      // Stats globales de la liga
  "managers": [ ... ],    // Array de 9 managers con sus stats
  "news": [ ... ],        // Periódicos generados (más reciente primero)
  "playersMap": { ... }   // { "NombreJugador": "url_foto" }
}
```

### `league`

```jsonc
{
  "name": "Sotano League",
  "season": "Temporada 2026",
  "dateRange": "2025-09-15 · 2026-06-09",
  "standings": [                          // Clasificación general
    { "rank": 1, "manager": "Dani", "points": 1450 }
  ],
  "poolStandings": [ ... ],               // Clasificación quinielas
  "managerOfMonth": {                     // Manager con más puntos última jornada
    "name": "Maldinillo",
    "subtitle": "...",
    "description": "..."
  },
  "playerOfMonth": {                      // Jugador con más puntos última jornada
    "name": "Mbappé", "team": "Real Madrid",
    "manager": "Maldinillo", "points": 18,
    "description": "..."
  },
  "latestHeadline": { ... },              // Primera card del periódico más reciente
  "mostExpensiveBuy": {                   // Compra más cara de mercado libre
    "player": "Mbappé", "manager": "Maldinillo", "amount": 131.4
  },
  "mostExpensiveClause": { ... },         // Clausulazo más caro
  "mostClausesGiven":    { "manager": "...", "count": 3 },   // Más clausulazos sufridos
  "mostClausesReceived": { "manager": "...", "count": 5 },   // Más clausulazos ejecutados
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
  "bestPlayerHistoric": { ... },
  "transferCount": 12,        // Número de compras realizadas
  "marketSpend": 450.5,       // Dinero total gastado en compras (millones)
  "market": {
    "mercado": 5,             // Compras en mercado libre
    "clausulas": 4,           // Clausulazos ejecutados
    "acuerdos": 3             // Acuerdos entre managers
  },
  "form": [72, 65, 80, 58, 71, 90, 68, 72],  // Puntos últimas 8 jornadas
  "comparison": {}            // Reservado para comparativas futuras
}
```

### `news[]`

Array de periódicos generados, ordenado del más reciente al más antiguo:

```jsonc
[
  {
    "date": "J17",
    "title": "¡La liga explota!",
    "subtitle": "Nada está decidido",
    "summary": "Frase resumen...",
    "cards": [                  // Cards del periódico (schema de SchemeValidator)
      {
        "tipo": "clasificacion",
        "jugador": null,
        "manager": null,
        "puntos": null,
        "dinero": null,
        "equipo": null,
        "titulo": "¡La liga explota!",
        "subtitulo": "Nada está decidido",
        "texto": ["Frase 1", "Frase 2", "Frase 3"]
      }
    ]
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

Contiene ~557 jugadores extraídos de `data/processed/jugadores.csv`.
