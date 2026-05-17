# CLAUDE.md — Pokemon ETL Pipeline

Este archivo le indica a Claude Code todo lo que necesita saber sobre este proyecto.

## ¿Qué es este proyecto?

**Pokemon Pipeline** es un pipeline ETL educativo construido en Python para el curso
*Python para Data Engineers* de DataHackers Academy.

Genera datos sintéticos de comparación y descarga stats de la PokeAPI (via `generate_data.py`),
los transforma, valida su calidad y los carga a DuckDB para análisis.

---

## Estructura del proyecto

```
pokemon-pipeline/
├── data/
│   ├── raw/                  # Datos generados por generate_data.py
│   │   ├── pokemon.json          — 150 Pokemon con stats base (de PokeAPI, formato JSON)
│   │   └── comparacion.csv       — 510 enfrentamientos sintéticos con suciedad intencional
│   ├── processed/            # Salida DuckDB (pokemon.duckdb)
│   └── rejected/             # Registros rechazados con timestamp (CSV)
├── src/
│   ├── extract.py            # Lee los CSV de data/raw/
│   ├── transform.py          # Limpieza, tipado, columnas derivadas, enriquecimiento
│   ├── validate.py           # pandera schemas + reglas de negocio + DQ report
│   └── load.py               # Carga a DuckDB con queries OLAP de demostración
├── tests/
│   └── test_transform.py     # 26 tests pytest de transform.py
├── notebooks/
│   ├── 01_exploracion.ipynb  # EDA de datos raw: comparacion.csv y pokemon.json
│   └── 02_duckdb.ipynb       # Exploración de tablas DuckDB post-pipeline
├── logs/                     # Logs de ejecución del pipeline (generados en runtime)
├── pipeline.py               # Orquestador principal E->T->V->L
├── generate_data.py          # Descarga PokeAPI + genera comparacion.csv sintético
├── requirements.txt
└── CLAUDE.md                 # Este archivo
```

---

## Cómo correr el proyecto

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Generar datos: descarga pokemon.csv desde PokeAPI y crea comparacion.csv (~2-3 min)
python generate_data.py

# 3. Correr pipeline completo
python pipeline.py

# Detener pipeline si la validación falla:
python pipeline.py --fail-on-validation

# 4. Correr tests
pytest tests/ -v

# 5. Abrir notebooks de exploración
jupyter notebook notebooks/01_exploracion.ipynb   # datos raw
jupyter notebook notebooks/02_duckdb.ipynb        # tablas DuckDB (requiere haber corrido pipeline.py)
```

---

## Módulos — descripción técnica

### `generate_data.py`
Genera los dos archivos de entrada en `data/raw/`. Solo necesita ejecutarse una vez.
- `_fetch_pokemon(pokemon_id)` — consulta `pokeapi.co/api/v2/pokemon/{id}` y extrae stats, effort, tipos, altura, peso
- `generate_pokemon(n=150)` — itera IDs 1-150 con tqdm y delay de 0.1s por request
- `generate_comparaciones(n=500)` — genera 500 filas sintéticas con suciedad intencional:
  - ~3% nulos en pokemon_a / pokemon_b
  - ~2% nulos en nivel_a / nivel_b
  - ~5% pokemon fuera de rango (0, -1, 151, 200, 999)
  - ~4% niveles fuera de rango (0, -1, 101, 150)
  - ~2% duplicados exactos (10 filas repetidas al final)
- `save_all()` — guarda `pokemon.json` y `comparacion.csv` en `data/raw/`
- Seeds fijados: `random.seed(42)`, `np.random.seed(42)` — resultados reproducibles

### `src/extract.py`
Lee solo archivos locales — sin llamadas a APIs en tiempo de pipeline.
- `extract_comparaciones(filepath=None)` — lee comparacion.csv con `dtype=str`
- `extract_pokemon(filepath=None)` — lee pokemon.json con `json.load` + `pd.DataFrame` (tipos nativos: int, float, None)
- `extract_all()` — entry point, retorna `{"comparaciones": df, "pokemon": df}`

### `src/transform.py`
Limpieza, enriquecimiento y cálculo de stats por nivel.
- `transform_comparaciones(df_raw)` — retorna `(df_valid, df_rejected)`:
  1. Registra duplicados exactos con `motivo_rechazo = "duplicado exacto"`
  2. Convierte columnas a numérico (`pd.to_numeric(..., errors="coerce")`)
  3. Separa inválidos (nulos + fuera de rango) con motivo detallado
- `transform_pokemon(df_raw)` — tipado numérico + columnas derivadas:
  - `total_stats` — suma de los 6 stats base
  - `height_m` — altura en metros (height / 10)
  - `weight_kg` — peso en kg (weight / 10)
  - `stat_role` — rol según stat dominante: `tank / physical_sweeper / special_sweeper / speedster`
  - `type2` — `None` se rellena con `"none"`
- `_calcular_stat(base, nivel, es_hp)` — fórmula oficial gen 3+ (sin IVs/EVs/naturaleza):
  - HP: `floor(2 * base * nivel / 100) + nivel + 10`
  - Otros: `floor(2 * base * nivel / 100) + 5`
- `enrich_comparaciones(df_comp, df_pokemon)` — merge con stats de cada Pokemon y calcula:
  - Stats reales al nivel dado (`a_hp_lv`, `b_speed_lv`, etc.)
  - `a_total_lv`, `b_total_lv` — suma de los 6 stats al nivel
  - `ganador` — nombre del ganador o `"empate"`
  - `poder_total`, `diferencia_poder`, `ventaja_pct`
- `build_tabla_comparacion(df_battles)` — tabla legible con pokemon + tipo + stats vs rival + resultado
- `transform_all(raw)` — entry point, retorna dict con 4 tablas

### `src/validate.py`
Validación de calidad con pandera + checks de negocio.
- `pokemon_schema` — valida dim_pokemon: id (1-150), stats > 0, total_stats (100-800)
- `battles_schema` — valida fact_battles: pokemon_a/b (1-150), nivel_a/b (1-100), ganador no nulo
- `validate_schema(df, schema, name)` — valida con `lazy=True`, imprime errores
- `assert_business_rules(df_battles, df_pokemon)` — checks de negocio:
  1. FK: todos los pokemon_a/b existen en dim_pokemon
  2. Coherencia del ganador (debe ser a_name, b_name o "empate")
  3. total_lv > 0 en todos los registros
  4. Outliers en total_stats base (IQR x1.5)
- `data_quality_report(dfs)` — resumen por tabla: filas, nulos, duplicados
- `save_rejected(df_rejected)` — guarda en `data/rejected/rejected_YYYYMMDD_HHMMSS.csv`
- `validate_all(transformed)` — entry point, retorna bool

### `src/load.py`
Carga a DuckDB local con queries OLAP de demostración.
- `load_to_duckdb(transformed)` — carga 4 tablas: `dim_pokemon`, `fact_battles`, `tabla_comparacion`, `rejected_records`
- Query OLAP 1: Top 10 Pokemon más usados con win_pct
- Query OLAP 2: Win rate promedio por tipo primario con avg_total_stats
- `_prepare_for_duckdb(df)` — convierte categoricals y listas a string
- `load_all(transformed)` — entry point
- DB path: `data/processed/pokemon.duckdb`

### `pipeline.py`
Orquestador con logging, manejo de errores y resumen final.
- `run_pipeline(fail_on_validation=False)` — ejecuta E->T->V->L
- Logging a stdout y a `logs/pipeline_YYYYMMDD_HHMMSS.log`
- Cada step tiene su propio `try/except` — un fallo en validate no detiene load
- `_print_summary(result, total_sec)` — tabla de [OK]/[WARN]/[FAIL] con duración por step
- CLI: `python pipeline.py [--fail-on-validation]`

### `notebooks/01_exploracion.ipynb`
EDA de las fuentes raw antes de cualquier transformación del pipeline.
- **Sección 1 — `comparacion.csv`**: nulos por columna, duplicados exactos, valores fuera de rango (pokemon 0/>150, nivel 0/>100), resumen de calidad con porcentajes, distribución de niveles válidos
- **Sección 2 — `pokemon.json`**: estructura raw con `json.load` (muestra primer registro completo con `json.dumps`), ejemplo de registro con `type2: null`, carga a DataFrame via `extract_pokemon()` mostrando dtypes nativos (int64/float64 vs todo-string del CSV)

### `notebooks/02_duckdb.ipynb`
Exploración interactiva de las tablas en DuckDB después de correr `pipeline.py`.
- Conexión con `duckdb.connect` y `SHOW TABLES`
- **`dim_pokemon`**: schema, top 10 por total_stats, stats promedio por tipo, distribución de stat_role
- **`fact_battles`**: distribución de resultados, top 10 por victorias, win rate por tipo primario, batallas más parejas
- **`tabla_comparacion`**: vista legible, conteo de resultados, buscador por Pokemon (celda editable con variable `POKEMON`)
- **`rejected_records`**: motivos de rechazo con conteos y ejemplos
- Sección de SQL libre con query de ejemplo (JOIN dim_pokemon + fact_battles)

---

## Datos — estructura de cada CSV

| Archivo | Formato | Campos |
|---------|---------|--------|
| `pokemon.json` | JSON (lista de objetos) | id, name, type1, type2, hp, attack, defense, special_attack, special_defense, speed, effort_hp, effort_attack, effort_defense, effort_special_attack, effort_special_defense, effort_speed, height, weight, base_experience |
| `comparacion.csv` | CSV | pokemon_a, nivel_a, pokemon_b, nivel_b |

### Tablas producidas por el pipeline

| Tabla | Descripción |
|-------|-------------|
| `dim_pokemon` | 150 Pokemon con stats base y columnas derivadas |
| `fact_battles` | Enfrentamientos válidos enriquecidos con stats al nivel |
| `tabla_comparacion` | Vista legible: pokemon + tipo + stats vs rival + resultado |
| `rejected_records` | Registros descartados con `motivo_rechazo` |

### Columnas derivadas (en transform)

| Columna | Origen | Descripción |
|---------|--------|-------------|
| `total_stats` | suma de 6 stats | Poder total base del Pokemon |
| `stat_role` | stat dominante | tank / physical_sweeper / special_sweeper / speedster |
| `height_m` | height / 10 | Altura en metros |
| `weight_kg` | weight / 10 | Peso en kilogramos |
| `a_*_lv` / `b_*_lv` | fórmula gen 3+ | Stat real al nivel del enfrentamiento |
| `ganador` | comparación total_lv | Nombre del Pokemon ganador o "empate" |
| `ventaja_pct` | diferencia / mínimo | Porcentaje de ventaja del ganador |

---

## Convenciones de código

- Cada módulo en `src/` tiene una función `*_all()` como entry point
- Los DataFrames crudos nunca se modifican in-place — siempre `df = df_raw.copy()`
- Los rechazados se separan con máscara booleana, nunca con excepciones
- Los prints de progreso usan el prefijo `[modulo:subtarea]`
- Los logs del pipeline van a `logs/pipeline_YYYYMMDD_HHMMSS.log`
- Windows: todos los prints usan `->` en lugar de `→` (encoding cp1252)

---

## Tests

`tests/test_transform.py` — 26 tests con pytest, sin mocks de base de datos:

| Grupo | Tests |
|-------|-------|
| Fórmula `_calcular_stat` | HP lv50, stat normal, lv1, lv100 |
| `transform_comparaciones` | Rechaza nulos, fuera de rango, duplicados, motivo siempre presente |
| `transform_pokemon` | total_stats, height_m, weight_kg, type2 relleno, stat_role |
| `enrich_comparaciones` | Stats al nivel, total_lv, poder_total, diferencia, ganador, empate |
| `build_tabla_comparacion` | Columnas presentes, resultado correcto, filas = battles |
| Edge cases | DataFrame vacío, todos inválidos |

---

## Ejercicios Claude Code para la clase

### Ejercicio 1 — Auditoría
```
Analiza src/transform.py y dime qué transformaciones podrían fallar
con datos reales en producción. Sé específico por función.
```

### Ejercicio 2 — Nueva columna
```
Agrega en src/transform.py una función classify_bst(df) que clasifique
cada Pokemon en tier (OU, UU, NU, Ubers) basado en su total_stats.
Agrégala al flujo de transform_all().
```

### Ejercicio 3 — Análisis de tipos
```
Crea en src/transform.py una función build_type_stats_pivot(pokemon) que
genere una tabla con stats promedio por tipo primario (type1).
Cárgala como tabla adicional en DuckDB.
```

### Ejercicio 4 — Libre
```
Revisa el pipeline completo y propón una mejora de arquitectura.
Impleméntala y explica qué problema resuelve.
```
