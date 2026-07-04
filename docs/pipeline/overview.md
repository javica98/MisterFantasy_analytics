# Visión general del pipeline

El sistema tiene **dos pipelines independientes** que comparten los mismos CSVs procesados como fuente de datos.

---

## Pipeline 1 — Periódico IA

Genera la portada del periódico de cada jornada.

```mermaid
sequenceDiagram
    participant S as scripts/run_newspaper.py
    participant GJ as generate_json.py
    participant GP as generate_prompt.py
    participant O as OrchestratorAgent (Groq)
    participant W as WriterAgent (Gemini)
    participant I as ImageAgent (CLIP)
    participant V as SchemeValidator

    S->>GJ: DataFrames CSV
    GJ-->>S: events_json
    S->>GP: events_json
    GP-->>S: prompt + bloques
    S->>O: prompt
    O->>W: genera JSON periódico
    W-->>O: JSON crudo
    O->>V: valida schema
    V-->>O: FinalJSON ✓
    O->>I: busca foto jugador
    I-->>O: foto descargada
    O-->>S: resultado completo
    S->>S: genera PNG portada
```

---

## Pipeline 2 — Web App

Regenera los datos estáticos de la web app.

```mermaid
sequenceDiagram
    participant S as regenerate_app_data.py
    participant GW as gameweek.csv
    participant GN as ganancias_clean.csv
    participant CL as clasificaciones.csv
    participant JU as jugadores.csv
    participant NJ as newspaper/json/
    participant OUT as web/data/app-data.json

    S->>GW: lee puntos por jornada
    S->>GN: lee transfers de mercado
    S->>CL: lee clasificación acumulada
    S->>JU: lee jugadores y fotos
    S->>NJ: lee periódicos generados
    S->>OUT: escribe JSON completo
```

---

## Datos que fluyen entre etapas

```mermaid
graph LR
    subgraph RAW["📁 data/raw/"]
        H1[dataMister.html]
        H2[gameweek.html]
        H3[mercado.html]
        H4[clasificacion.html]
        H5[quiniela.html]
    end

    subgraph PROCESSED["📁 data/processed/"]
        C1[gameweek.csv]
        C2[ganancias_clean.csv]
        C3[clasificaciones.csv]
        C4[quiniela.csv]
        C5[jugadores.csv]
    end

    subgraph OUTPUT["📁 Outputs"]
        P1[newspaper/json/jornada_XX.json]
        P2[newspaper/new/FECHA_news.png]
        P3[web/data/app-data.json]
        P4[dashboards/reports/report.pdf]
    end

    H1 & H2 & H3 & H4 & H5 -->|run_extraction.py + run_preprocess.py| C1 & C2 & C3 & C4 & C5
    C1 & C2 & C3 & C4 -->|run_newspaper.py| P1 & P2
    C1 & C2 & C3 & C4 & C5 & P1 -->|regenerate_app_data.py| P3
    C1 & C2 & C3 -->|run_dashboard.py| P4
```

---

## Orden de ejecución recomendado

| Paso | Script | Requiere |
|------|--------|----------|
| 1 | `run_extraction.py` | HTMLs en `data/raw/` |
| 2 | `run_preprocess.py` | Paso 1 completado |
| 3 | `run_newspaper.py` | Paso 2 + API keys |
| 4 | `regenerate_app_data.py` | Paso 2 (paso 3 opcional) |

