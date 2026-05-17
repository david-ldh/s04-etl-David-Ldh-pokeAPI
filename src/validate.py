"""
Pokemon Pipeline — Módulo Validate
Validación de calidad de datos con pandera + asserts de negocio
"""

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

from datetime import datetime
from pathlib import Path

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema, Check

REJECTED_DIR = Path(__file__).parent.parent / "data" / "rejected"
REJECTED_DIR.mkdir(parents=True, exist_ok=True)

TIPOS_VALIDOS = [
    "normal", "fire", "water", "electric", "grass", "ice",
    "fighting", "poison", "ground", "flying", "psychic", "bug",
    "rock", "ghost", "dragon", "dark", "steel", "fairy", "none"
]


# ─── SCHEMAS PANDERA ─────────────────────────────────────────────────────────

pokemon_schema = DataFrameSchema(
    {
        "id":              Column(int, Check.in_range(1, 150),  nullable=False),
        "name":            Column(str, Check(lambda s: s.str.len() > 0), nullable=False),
        "type1":           Column(str, Check.isin(TIPOS_VALIDOS), nullable=False),
        "type2":           Column(str, Check.isin(TIPOS_VALIDOS), nullable=False),
        "hp":              Column(int, Check.greater_than(0),   nullable=False),
        "attack":          Column(int, Check.greater_than(0),   nullable=False),
        "defense":         Column(int, Check.greater_than(0),   nullable=False),
        "special_attack":  Column(int, Check.greater_than(0),   nullable=False),
        "special_defense": Column(int, Check.greater_than(0),   nullable=False),
        "speed":           Column(int, Check.greater_than(0),   nullable=False),
        "total_stats":     Column(int, Check.in_range(100, 800), nullable=False),
    },
    coerce=True,
    strict=False
)

battles_schema = DataFrameSchema(
    {
        "pokemon_a":   Column(int, Check.in_range(1, 150), nullable=False),
        "pokemon_b":   Column(int, Check.in_range(1, 150), nullable=False),
        "nivel_a":     Column(int, Check.in_range(1, 100), nullable=False),
        "nivel_b":     Column(int, Check.in_range(1, 100), nullable=False),
        "a_name":      Column(str, nullable=False),
        "b_name":      Column(str, nullable=False),
        "a_total_lv":  Column(int, Check.greater_than(0),  nullable=False),
        "b_total_lv":  Column(int, Check.greater_than(0),  nullable=False),
        "ganador":     Column(str, nullable=False),
    },
    coerce=True,
    strict=False
)


# ─── VALIDAR CON PANDERA ─────────────────────────────────────────────────────

def validate_schema(df: pd.DataFrame, schema: DataFrameSchema, name: str) -> bool:
    try:
        schema.validate(df, lazy=True)
        print(f"[validate] OK {name}: schema correcto")
        return True
    except pa.errors.SchemaErrors as e:
        print(f"[validate] ERROR {name}: {len(e.failure_cases)} errores de schema")
        print(e.failure_cases[["schema_context", "column", "check", "failure_case"]].head(10).to_string())
        return False


# ─── ASSERTS DE NEGOCIO ───────────────────────────────────────────────────────

def assert_business_rules(df_battles: pd.DataFrame, df_pokemon: pd.DataFrame) -> dict:
    """
    Checks de negocio que van más allá del schema.
    """
    results = {}

    # 1. Todos los pokemon_a y pokemon_b deben existir en dim_pokemon
    ids_validos = set(df_pokemon["id"])
    orphans_a = df_battles[~df_battles["pokemon_a"].isin(ids_validos)]
    orphans_b = df_battles[~df_battles["pokemon_b"].isin(ids_validos)]
    results["orphan_pokemon_a"] = len(orphans_a)
    results["orphan_pokemon_b"] = len(orphans_b)
    if len(orphans_a) + len(orphans_b) > 0:
        print(f"[validate] WARN {len(orphans_a)} battles con pokemon_a sin match | {len(orphans_b)} con pokemon_b sin match")
    else:
        print("[validate] OK FK pokemon_a y pokemon_b integros")

    # 2. El ganador debe ser a_name, b_name o "empate"
    nombres_validos = set(df_battles["a_name"]) | set(df_battles["b_name"]) | {"empate"}
    ganadores_invalidos = df_battles[~df_battles["ganador"].isin(nombres_validos)]
    results["ganadores_invalidos"] = len(ganadores_invalidos)
    if len(ganadores_invalidos) > 0:
        print(f"[validate] WARN {len(ganadores_invalidos)} battles con ganador invalido")
    else:
        print("[validate] OK Campo ganador coherente")

    # 3. total_stats al nivel debe ser mayor que cero
    stats_cero = df_battles[(df_battles["a_total_lv"] <= 0) | (df_battles["b_total_lv"] <= 0)]
    results["stats_cero"] = len(stats_cero)
    if len(stats_cero) > 0:
        print(f"[validate] WARN {len(stats_cero)} battles con total_lv <= 0")
    else:
        print("[validate] OK Stats calculados al nivel son positivos")

    # 4. Outliers en total_stats base (IQR)
    Q1 = df_pokemon["total_stats"].quantile(0.25)
    Q3 = df_pokemon["total_stats"].quantile(0.75)
    IQR = Q3 - Q1
    outliers = df_pokemon[
        (df_pokemon["total_stats"] < Q1 - 1.5 * IQR) |
        (df_pokemon["total_stats"] > Q3 + 1.5 * IQR)
    ]
    results["outliers_total_stats"] = len(outliers)
    print(f"[validate] INFO Outliers en total_stats (IQR x1.5): {len(outliers)} Pokemon")
    if len(outliers) > 0:
        print(f"           {outliers[['name', 'total_stats']].to_string(index=False)}")

    return results


# ─── DATA QUALITY REPORT ─────────────────────────────────────────────────────

def data_quality_report(dfs: dict) -> pd.DataFrame:
    """
    Genera un resumen de calidad por DataFrame: filas, nulos, duplicados.
    """
    rows = []
    for name, df in dfs.items():
        if df is None or df.empty:
            continue
        rows.append({
            "tabla":              name,
            "total_filas":        len(df),
            "columnas":           df.shape[1],
            "filas_duplicadas":   df.duplicated().sum(),
            "pct_nulos_promedio": round(df.isna().mean().mean() * 100, 2),
            "columna_mas_nulos":  df.isna().mean().idxmax() if df.isna().any().any() else "ninguna",
            "pct_nulos_peor_col": round(df.isna().mean().max() * 100, 2),
        })

    report = pd.DataFrame(rows)
    print("\n[validate] DATA QUALITY REPORT")
    print(report.to_string(index=False))
    return report


# ─── GUARDAR RECHAZADOS ───────────────────────────────────────────────────────

def save_rejected(df_rejected: pd.DataFrame):
    if df_rejected.empty:
        print("[validate] Sin registros rechazados que guardar")
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REJECTED_DIR / f"rejected_{ts}.csv"
    df_rejected.to_csv(path, index=False)
    print(f"[validate] Rechazados guardados: {path} ({len(df_rejected)} filas)")


# ─── VALIDATE ALL (entry point) ──────────────────────────────────────────────

def validate_all(transformed: dict) -> bool:
    print("\n" + "=" * 60)
    print("  VALIDATE — Checks de calidad y negocio")
    print("=" * 60)

    ok = True
    ok &= validate_schema(transformed["dim_pokemon"],  pokemon_schema,  "dim_pokemon")
    ok &= validate_schema(transformed["fact_battles"], battles_schema,  "fact_battles")

    print()
    assert_business_rules(transformed["fact_battles"], transformed["dim_pokemon"])

    print()
    data_quality_report({
        "dim_pokemon":       transformed["dim_pokemon"],
        "fact_battles":      transformed["fact_battles"],
        "tabla_comparacion": transformed["tabla_comparacion"],
        "rejected":          transformed["rejected_records"],
    })

    save_rejected(transformed["rejected_records"])
    return ok


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.extract import extract_all
    from src.transform import transform_all

    raw = extract_all()
    transformed = transform_all(raw)
    validate_all(transformed)
