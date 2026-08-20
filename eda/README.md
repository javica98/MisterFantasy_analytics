# eda — Fantasy Bidding Intelligence

Subproyecto de Machine Learning para predecir el comportamiento del mercado de jugadores.

> **Nota:** estos notebooks también existen (copiados) en `docs/eda/`, porque
> MkDocs (`mkdocs-jupyter`) solo puede renderizar archivos dentro de `docs_dir`.
> Las dos copias pueden divergir si se re-ejecuta uno sin actualizar el otro
> (ya ha pasado). Antes de publicar la documentación, copia la versión
> re-ejecutada de `eda/` a `docs/eda/` para mantenerlas sincronizadas.

## Notebooks (ejecutar en orden)

| Notebook | Descripción | Estado |
|----------|-------------|--------|
| `01_auditoria_dataset.ipynb` | Calidad del dataset: nulos, duplicados, outliers, estadística descriptiva | ✅ |
| `02_eda_exploratoria.ipynb` | EDA orientado a predicción: señal de cada variable hacia el target | ✅ |
| `03_feature_engineering.ipynb` | Escalado, encoding, features derivadas, winsorización | ✅ (crash arreglado) |
| `04_modelos.ipynb` | Logistic Regression, Random Forest, XGBoost, LightGBM + backtesting temporal | ✅ |

## Dataset de entrada

Tabla `data_model` de `data/mister.db` (generada por `scripts/run_modelprocess.py`, temporada `2025-26`), exportada a CSV para que los notebooks la lean con `pandas.read_csv` normal:

```bash
python scripts/export_db_to_csv.py 2025-26
# -> data/export/2025-26/data_model.csv
```

Los notebooks leen `../data/processed/data_model.csv` directamente (no pasan por `file_utils.py`/`db.py`), así que hay que copiar el export ahí antes de ejecutarlos:

```bash
cp data/export/2025-26/data_model.csv data/processed/data_model.csv
```

## Dataset de salida

`results/03_dataset_features_modelado.csv` — generado por el notebook 03, consumido por el 04

## Resultados

- **Clasificación** (¿recibe pujas?): Random Forest ROC-AUC **0.9998**, F1 **0.989** (threshold 0.36)
- **Regresión** (¿cuánto se paga?): Random Forest R² **0.868**, MAE **1.28M**
