"""
Pokemon Pipeline — Módulo Load
Carga a DuckDB local con query OLAP de demostración
"""

import duckdb
import pandas as pd
from pathlib import Path

DUCKDB_PATH = Path(__file__).parent.parent / "data" / "processed" / "pokemon.duckdb"
DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ─── DUCKDB ───────────────────────────────────────────────────────────────────

def load_to_duckdb(transformed: dict) -> bool:
    """
    Carga las tablas transformadas a DuckDB local.
    DuckDB puede leer DataFrames directamente — sin conversión extra.
    """
    print(f"\n[load:duckdb] Conectando a {DUCKDB_PATH} ...")
    try:
        con = duckdb.connect(str(DUCKDB_PATH))

        tables = {
            "dim_pokemon":       transformed["dim_pokemon"],
            "fact_battles":      transformed["fact_battles"],
            "tabla_comparacion": transformed["tabla_comparacion"],
            "rejected_records":  transformed["rejected_records"],
        }

        for table_name, df in tables.items():
            if df.empty:
                print(f"[load:duckdb] {table_name}: vacio, se omite")
                continue

            df_duck = _prepare_for_duckdb(df)
            con.execute(f"DROP TABLE IF EXISTS {table_name}")
            con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_duck")
            count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"[load:duckdb] {table_name}: {count:,} filas cargadas")

        # ── Queries OLAP de demostración ─────────────────────────────────────
        print("\n[load:duckdb] Query OLAP 1 — Top 10 Pokemon mas usados en batallas:")
        q1 = con.execute("""
            SELECT battles.name, p.type1, p.type2, battles.total_wins, battles.total_battles,
                   ROUND(battles.total_wins * 100.0 / battles.total_battles, 1) AS win_pct
            FROM (
                SELECT a_name AS name, COUNT(*) AS total_battles,
                       SUM(CASE WHEN ganador = a_name THEN 1 ELSE 0 END) AS total_wins
                FROM fact_battles GROUP BY a_name
                UNION ALL
                SELECT b_name, COUNT(*),
                       SUM(CASE WHEN ganador = b_name THEN 1 ELSE 0 END)
                FROM fact_battles GROUP BY b_name
            ) battles
            JOIN dim_pokemon p ON p.name = battles.name
            ORDER BY total_battles DESC
            LIMIT 10
        """).df()
        print(q1.to_string(index=False))

        print("\n[load:duckdb] Query OLAP 2 — Win rate promedio por tipo primario:")
        q2 = con.execute("""
            SELECT p.type1,
                   COUNT(DISTINCT battles.name)                           AS pokemon_count,
                   ROUND(AVG(p.total_stats), 1)                           AS avg_total_stats,
                   SUM(battles.total_wins)                                AS total_wins,
                   SUM(battles.total_battles)                             AS total_battles,
                   ROUND(SUM(battles.total_wins) * 100.0 / SUM(battles.total_battles), 1) AS win_pct
            FROM (
                SELECT a_name AS name,
                       SUM(CASE WHEN ganador = a_name THEN 1 ELSE 0 END) AS total_wins,
                       COUNT(*) AS total_battles
                FROM fact_battles GROUP BY a_name
                UNION ALL
                SELECT b_name,
                       SUM(CASE WHEN ganador = b_name THEN 1 ELSE 0 END),
                       COUNT(*)
                FROM fact_battles GROUP BY b_name
            ) battles
            JOIN dim_pokemon p ON p.name = battles.name
            GROUP BY p.type1
            ORDER BY win_pct DESC
        """).df()
        print(q2.to_string(index=False))

        con.close()
        print(f"\n[load:duckdb] Archivo guardado: {DUCKDB_PATH}")
        return True

    except Exception as e:
        print(f"[load:duckdb] Error: {e}")
        return False


def _prepare_for_duckdb(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if isinstance(df[col].dtype, pd.CategoricalDtype):
            df[col] = df[col].astype(str)
        if df[col].dtype == object:
            sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            if isinstance(sample, (list, dict)):
                df[col] = df[col].astype(str)
    return df


# ─── LOAD ALL (entry point) ───────────────────────────────────────────────────

def load_all(transformed: dict) -> dict:
    print("\n" + "=" * 60)
    print("  LOAD — Cargando a destinos")
    print("=" * 60)

    return {"duckdb": load_to_duckdb(transformed)}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.extract import extract_all
    from src.transform import transform_all

    raw = extract_all()
    transformed = transform_all(raw)
    load_all(transformed)
