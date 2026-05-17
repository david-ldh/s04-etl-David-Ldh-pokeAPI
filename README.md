# Pokemon ETL Pipeline

Pipeline ETL educativo construido en Python para el curso *Python para Data Engineers* de DataHackers Academy.

Descarga datos de la [PokeAPI](https://pokeapi.co), genera comparaciones sintéticas con suciedad intencional, los transforma, valida su calidad y los carga a DuckDB para análisis.

---

## Requisitos

- Python 3.10+
- Conexión a internet (solo para `generate_data.py`)

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd pokemon-pipeline

# 2. Crear entorno virtual e instalar dependencias
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
```

---

## Uso

### 1. Generar datos de entrada

Descarga los 150 Pokemon de la PokeAPI y genera comparaciones sintéticas (~2-3 min):

```bash
python generate_data.py
```

Genera en `data/raw/`:
- `pokemon.json` — 150 Pokemon con stats base (de PokeAPI)
- `comparacion.csv` — 510 enfrentamientos sintéticos con suciedad intencional

### 2. Correr el pipeline completo

```bash
python pipeline.py
```

Ejecuta Extract -> Transform -> Validate -> Load y genera:
- `data/processed/pokemon.duckdb` — base de datos analítica con 4 tablas
- `data/rejected/rejected_*.csv` — registros descartados con motivo
- `logs/pipeline_*.log` — log completo de ejecución

Para detener el pipeline si la validación falla:

```bash
python pipeline.py --fail-on-validation
```

### 3. Correr los tests

```bash
pytest tests/ -v
```

### 4. Explorar los datos con Jupyter

```bash
jupyter notebook
```

- `notebooks/01_exploracion.ipynb` — EDA de los datos raw (comparacion.csv y pokemon.json)
- `notebooks/02_duckdb.ipynb` — Exploración de las tablas en DuckDB (requiere haber corrido el pipeline)

---

## Estructura del proyecto

```
pokemon-pipeline/
├── data/
│   ├── raw/                  # Generado por generate_data.py
│   ├── processed/            # DuckDB generado por pipeline.py
│   └── rejected/             # Registros rechazados con timestamp
├── src/
│   ├── extract.py            # Lee CSV y JSON de data/raw/
│   ├── transform.py          # Limpieza, tipado, columnas calculadas
│   ├── validate.py           # Schemas pandera + reglas de negocio
│   └── load.py               # Carga a DuckDB
├── tests/
│   └── test_transform.py     # 26 tests pytest
├── notebooks/
│   ├── 01_exploracion.ipynb  # EDA datos raw
│   └── 02_duckdb.ipynb       # Exploración DuckDB
├── pipeline.py               # Orquestador E->T->V->L
├── generate_data.py          # Genera datos de entrada
└── requirements.txt
```

---

## Tablas en DuckDB

| Tabla | Filas | Descripción |
|-------|-------|-------------|
| `dim_pokemon` | 150 | Pokemon con stats base y columnas calculadas |
| `fact_battles` | ~377 | Enfrentamientos válidos con stats al nivel |
| `tabla_comparacion` | ~377 | Vista legible pokemon vs rival con resultado |
| `rejected_records` | ~133 | Registros descartados con motivo de rechazo |
