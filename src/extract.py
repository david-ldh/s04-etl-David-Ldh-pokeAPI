"""
Pokemon Pipeline — Módulo Extract
Dos fuentes locales: comparacion.csv + pokemon.json (generados por generate_data.py)
"""

import json
import pandas as pd
from pathlib import Path

# ─── PATHS ────────────────────────────────────────────────────────────────────

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


# ─── 1. EXTRACT: COMPARACIONES desde CSV ─────────────────────────────────────

def extract_comparaciones(filepath: str = None) -> pd.DataFrame:
    """
    Lee comparacion.csv con dtype=str para preservar suciedad original.
    El DE ve los datos tal como vienen — nulos, fuera de rango y duplicados incluidos.
    """
    path = filepath or RAW_DIR / "comparacion.csv"
    if not path.exists() if isinstance(path, Path) else not Path(path).exists():
        raise FileNotFoundError(f"[extract] {path} no encontrado. Ejecuta generate_data.py primero.")
    df = pd.read_csv(path, dtype=str)
    print(f"[extract] comparacion.csv -> {df.shape[0]:,} filas, {df.shape[1]} columnas")
    return df


# ─── 2. EXTRACT: POKEMON desde JSON local ────────────────────────────────────

def extract_pokemon(filepath: str = None) -> pd.DataFrame:
    """
    Lee pokemon.json generado por generate_data.py.
    El JSON preserva los tipos nativos de la API (int, float, None).
    """
    path = Path(filepath) if filepath else RAW_DIR / "pokemon.json"
    if not path.exists():
        raise FileNotFoundError(f"[extract] {path} no encontrado. Ejecuta generate_data.py primero.")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    print(f"[extract] pokemon.json -> {df.shape[0]:,} filas, {df.shape[1]} columnas")
    return df


# ─── EXTRACT ALL (entry point) ────────────────────────────────────────────────

def extract_all() -> dict:
    """
    Ejecuta todos los extracts y retorna un dict con los DataFrames crudos.
    """
    print("=" * 60)
    print("  EXTRACT — Leyendo fuentes de datos")
    print("=" * 60)

    return {
        "comparaciones": extract_comparaciones(),
        "pokemon":       extract_pokemon(),
    }


if __name__ == "__main__":
    data = extract_all()
    for name, df in data.items():
        print(f"\n{name}:")
        print(df.head(3).to_string())
        print(f"   dtypes: {df.dtypes.to_dict()}")
