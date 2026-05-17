"""
Pokemon Pipeline — Módulo Transform
Limpieza, tipado, columnas calculadas y enriquecimiento del enfrentamiento
"""

import numpy as np
import pandas as pd

STAT_COLS = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]


# ─── TRANSFORM: COMPARACIONES ────────────────────────────────────────────────

def _motivo_rechazo(row) -> str:
    reasons = []
    if pd.isna(row["pokemon_a"]):
        reasons.append("pokemon_a nulo")
    elif not (1 <= row["pokemon_a"] <= 150):
        reasons.append(f"pokemon_a fuera de rango ({row['pokemon_a']})")
    if pd.isna(row["pokemon_b"]):
        reasons.append("pokemon_b nulo")
    elif not (1 <= row["pokemon_b"] <= 150):
        reasons.append(f"pokemon_b fuera de rango ({row['pokemon_b']})")
    if pd.isna(row["nivel_a"]):
        reasons.append("nivel_a nulo")
    elif not (1 <= row["nivel_a"] <= 100):
        reasons.append(f"nivel_a fuera de rango ({row['nivel_a']})")
    if pd.isna(row["nivel_b"]):
        reasons.append("nivel_b nulo")
    elif not (1 <= row["nivel_b"] <= 100):
        reasons.append(f"nivel_b fuera de rango ({row['nivel_b']})")
    return " | ".join(reasons) if reasons else "desconocido"


def transform_comparaciones(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Limpia comparaciones: tipado numérico, rango válido, duplicados.
    Retorna: (df_valid, df_rejected)
    """
    df = df_raw.copy()

    # ── 1. Identificar y registrar duplicados ────────────────────────────────
    mask_dupes = df.duplicated(keep="first")
    df_dupes = df[mask_dupes].copy()
    df_dupes["motivo_rechazo"] = "duplicado exacto"
    df = df[~mask_dupes].copy()
    print(f"[transform:comparaciones] Duplicados registrados: {len(df_dupes)}")

    # ── 2. Tipado numérico ───────────────────────────────────────────────────
    for col in ["pokemon_a", "nivel_a", "pokemon_b", "nivel_b"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── 3. Separar válidos de rechazados (nulos + fuera de rango) ────────────
    mask_invalid = (
        df["pokemon_a"].isna() | ~df["pokemon_a"].between(1, 150) |
        df["pokemon_b"].isna() | ~df["pokemon_b"].between(1, 150) |
        df["nivel_a"].isna()   | ~df["nivel_a"].between(1, 100)   |
        df["nivel_b"].isna()   | ~df["nivel_b"].between(1, 100)
    )

    df_invalid = df[mask_invalid].copy()
    df_invalid["motivo_rechazo"] = df[mask_invalid].apply(_motivo_rechazo, axis=1)

    df_valid = df[~mask_invalid].copy()
    df_valid[["pokemon_a", "pokemon_b"]] = df_valid[["pokemon_a", "pokemon_b"]].astype(int)
    df_valid[["nivel_a", "nivel_b"]]     = df_valid[["nivel_a", "nivel_b"]].astype(int)

    # ── 4. Unir todos los rechazados en un solo DataFrame ────────────────────
    df_rejected = pd.concat([df_dupes, df_invalid], ignore_index=True)

    print(f"[transform:comparaciones] Validos: {len(df_valid):,} | Rechazados: {len(df_rejected):,} (dupes: {len(df_dupes)}, invalidos: {len(df_invalid)})")
    return df_valid, df_rejected


# ─── TRANSFORM: POKEMON ──────────────────────────────────────────────────────

_STAT_ROLE_MAP = {
    "hp":             "tank",
    "defense":        "tank",
    "special_defense":"tank",
    "attack":         "physical_sweeper",
    "special_attack": "special_sweeper",
    "speed":          "speedster",
}


def transform_pokemon(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Enriquece el DataFrame de Pokemon con columnas calculadas.
    Los datos vienen limpios de la API — no hay suciedad que corregir.
    """
    df = df_raw.copy()

    # ── 1. Tipado numérico (viene como str desde el CSV) ─────────────────────
    num_cols = STAT_COLS + [
        "id", "height", "weight", "base_experience",
        "effort_hp", "effort_attack", "effort_defense",
        "effort_special_attack", "effort_special_defense", "effort_speed",
    ]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── 2. Columnas derivadas ────────────────────────────────────────────────
    df["total_stats"] = df[STAT_COLS].sum(axis=1)
    df["height_m"]    = df["height"] / 10
    df["weight_kg"]   = df["weight"] / 10

    # ── 2. Rol basado en el stat dominante ───────────────────────────────────
    df["stat_role"] = df[STAT_COLS].idxmax(axis=1).map(_STAT_ROLE_MAP).fillna("balanced")

    # ── 3. Tipo secundario: None -> "none" para claridad en queries ──────────
    df["type2"] = df["type2"].fillna("none")

    print(f"[transform:pokemon] {len(df):,} Pokemon enriquecidos")
    return df


# ─── ENRICH: CALCULAR STATS POR NIVEL ────────────────────────────────────────

def _calcular_stat(base: int, nivel: int, es_hp: bool = False) -> int:
    """
    Formula oficial (gen 3+, sin IVs/EVs/naturaleza).
      HP    = floor(2 * base * nivel / 100) + nivel + 10
      Otros = floor(2 * base * nivel / 100) + 5
    """
    base_calc = int(2 * base * nivel / 100)
    return base_calc + nivel + 10 if es_hp else base_calc + 5


def enrich_comparaciones(
    df_comp: pd.DataFrame,
    df_pokemon: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge comparaciones con stats de Pokemon A y B,
    calcula sus stats reales al nivel dado y determina el ganador.
    """
    pk = df_pokemon.set_index("id")

    # ── Join Pokemon A ────────────────────────────────────────────────────────
    cols_base = ["name", "type1", "type2", "stat_role", "total_stats"] + STAT_COLS
    df = df_comp.merge(
        pk[cols_base].add_prefix("a_"),
        left_on="pokemon_a", right_index=True,
        how="left"
    )

    # ── Join Pokemon B ────────────────────────────────────────────────────────
    df = df.merge(
        pk[cols_base].add_prefix("b_"),
        left_on="pokemon_b", right_index=True,
        how="left"
    )

    # ── Calcular stats reales al nivel dado (vectorizado) ────────────────────
    for stat in STAT_COLS:
        es_hp = stat == "hp"
        base_a = (2 * df[f"a_{stat}"] * df["nivel_a"]) // 100
        base_b = (2 * df[f"b_{stat}"] * df["nivel_b"]) // 100
        if es_hp:
            df[f"a_{stat}_lv"] = (base_a + df["nivel_a"] + 10).astype(int)
            df[f"b_{stat}_lv"] = (base_b + df["nivel_b"] + 10).astype(int)
        else:
            df[f"a_{stat}_lv"] = (base_a + 5).astype(int)
            df[f"b_{stat}_lv"] = (base_b + 5).astype(int)

    # ── Total stats al nivel dado ─────────────────────────────────────────────
    lv_cols_a = [f"a_{s}_lv" for s in STAT_COLS]
    lv_cols_b = [f"b_{s}_lv" for s in STAT_COLS]
    df["a_total_lv"] = df[lv_cols_a].sum(axis=1)
    df["b_total_lv"] = df[lv_cols_b].sum(axis=1)

    # ── Ganador por total de stats al nivel ───────────────────────────────────
    df["ganador"] = np.where(
        df["a_total_lv"] > df["b_total_lv"], df["a_name"],
        np.where(df["b_total_lv"] > df["a_total_lv"], df["b_name"], "empate")
    )

    # ── Poder total del enfrentamiento y margen del ganador ───────────────────
    df["poder_total"]      = df["a_total_lv"] + df["b_total_lv"]
    df["diferencia_poder"] = (df["a_total_lv"] - df["b_total_lv"]).abs()
    df["ventaja_pct"]      = (
        df["diferencia_poder"] / df[["a_total_lv", "b_total_lv"]].min(axis=1) * 100
    ).round(1)

    print(f"[transform:enrich] {len(df):,} enfrentamientos enriquecidos")
    return df


# ─── TABLA COMPARACION ENRIQUECIDA ───────────────────────────────────────────

def build_tabla_comparacion(df_battles: pd.DataFrame) -> pd.DataFrame:
    """
    Tabla legible con una fila por enfrentamiento:
    pokemon + tipo + stats al nivel vs contrincante + tipo + stats al nivel + resultado.
    """
    df = pd.DataFrame({
        # ── Pokemon A ────────────────────────────────────────────────────────
        "pokemon_id":          df_battles["pokemon_a"],
        "pokemon":             df_battles["a_name"],
        "tipo1":               df_battles["a_type1"],
        "tipo2":               df_battles["a_type2"],
        "nivel":               df_battles["nivel_a"],
        "hp":                  df_battles["a_hp_lv"],
        "attack":              df_battles["a_attack_lv"],
        "defense":             df_battles["a_defense_lv"],
        "special_attack":      df_battles["a_special_attack_lv"],
        "special_defense":     df_battles["a_special_defense_lv"],
        "speed":               df_battles["a_speed_lv"],
        "poder":               df_battles["a_total_lv"],
        # ── Pokemon B (contrincante) ──────────────────────────────────────────
        "rival_id":            df_battles["pokemon_b"],
        "rival":               df_battles["b_name"],
        "rival_tipo1":         df_battles["b_type1"],
        "rival_tipo2":         df_battles["b_type2"],
        "rival_nivel":         df_battles["nivel_b"],
        "rival_hp":            df_battles["b_hp_lv"],
        "rival_attack":        df_battles["b_attack_lv"],
        "rival_defense":       df_battles["b_defense_lv"],
        "rival_special_attack":df_battles["b_special_attack_lv"],
        "rival_special_defense":df_battles["b_special_defense_lv"],
        "rival_speed":         df_battles["b_speed_lv"],
        "rival_poder":         df_battles["b_total_lv"],
        # ── Resultado ────────────────────────────────────────────────────────
        "poder_total":         df_battles["poder_total"],
        "diferencia_poder":    df_battles["diferencia_poder"],
        "ventaja_pct":         df_battles["ventaja_pct"],
        "ganador":             df_battles["ganador"],
        "resultado":           np.where(
                                   df_battles["ganador"] == df_battles["a_name"], "gana",
                                   np.where(df_battles["ganador"] == "empate", "empate", "pierde")
                               ),
    })

    print(f"[transform:tabla_comparacion] {len(df):,} filas")
    return df


# ─── TRANSFORM ALL (entry point) ─────────────────────────────────────────────

def transform_all(raw: dict) -> dict:
    print("\n" + "=" * 60)
    print("  TRANSFORM — Limpiando y transformando")
    print("=" * 60)

    df_pokemon = transform_pokemon(raw["pokemon"])
    df_comp_valid, df_comp_rejected = transform_comparaciones(raw["comparaciones"])
    df_enriched = enrich_comparaciones(df_comp_valid, df_pokemon)
    df_tabla    = build_tabla_comparacion(df_enriched)

    return {
        "dim_pokemon":        df_pokemon,
        "fact_battles":       df_enriched,
        "tabla_comparacion":  df_tabla,
        "rejected_records":   df_comp_rejected,
    }


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.extract import extract_all

    raw = extract_all()
    transformed = transform_all(raw)

    for name, df in transformed.items():
        print(f"\n{name}: {df.shape}")
        print(df.head(3).to_string())
