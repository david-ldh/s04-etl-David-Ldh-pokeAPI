"""
Pokemon Pipeline — Tests de transformación con pytest
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.transform import (
    transform_comparaciones,
    transform_pokemon,
    enrich_comparaciones,
    build_tabla_comparacion,
    _calcular_stat,
    STAT_COLS,
)


# ─── FIXTURES ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_comparaciones():
    return pd.DataFrame({
        "pokemon_a": ["25",   "6",    None,  "0",    "25",  "25"],   # nulo y fuera de rango
        "nivel_a":   ["50",   "75",   "50",  "50",   "50",  "50"],
        "pokemon_b": ["6",    "25",   "6",   "6",    "0",   "6"],    # fuera de rango
        "nivel_b":   ["75",   "50",   "75",  "75",   "75",  "101"],  # nivel fuera de rango
    })


@pytest.fixture
def sample_comparaciones_con_dupes():
    return pd.DataFrame({
        "pokemon_a": ["25", "6",  "25"],   # fila 0 y 2 son duplicados
        "nivel_a":   ["50", "75", "50"],
        "pokemon_b": ["6",  "25", "6"],
        "nivel_b":   ["75", "50", "75"],
    })


@pytest.fixture
def sample_pokemon():
    return pd.DataFrame({
        "id":                     ["25",  "6"],
        "name":                   ["pikachu", "charizard"],
        "type1":                  ["electric", "fire"],
        "type2":                  [None, "flying"],
        "hp":                     ["35",  "78"],
        "attack":                 ["55",  "84"],
        "defense":                ["40",  "78"],
        "special_attack":         ["50",  "109"],
        "special_defense":        ["50",  "85"],
        "speed":                  ["90",  "100"],
        "effort_hp":              ["0",   "0"],
        "effort_attack":          ["0",   "0"],
        "effort_defense":         ["0",   "0"],
        "effort_special_attack":  ["0",   "3"],
        "effort_special_defense": ["0",   "0"],
        "effort_speed":           ["2",   "0"],
        "height":                 ["4",   "17"],
        "weight":                 ["60",  "905"],
        "base_experience":        ["112", "267"],
    })


# ─── TESTS: FORMULA DE STATS ─────────────────────────────────────────────────

def test_calcular_stat_hp():
    # HP lv50 con base 35: floor(2*35*50/100) + 50 + 10 = 35 + 50 + 10 = 95
    assert _calcular_stat(35, 50, es_hp=True) == 95


def test_calcular_stat_otros():
    # Speed lv50 con base 90: floor(2*90*50/100) + 5 = 90 + 5 = 95
    assert _calcular_stat(90, 50, es_hp=False) == 95


def test_calcular_stat_nivel_1():
    # HP nivel 1 con base 45: floor(2*45*1/100) + 1 + 10 = 0 + 11 = 11
    assert _calcular_stat(45, 1, es_hp=True) == 11


def test_calcular_stat_nivel_100():
    # Attack nivel 100 con base 55: floor(2*55*100/100) + 5 = 110 + 5 = 115
    assert _calcular_stat(55, 100, es_hp=False) == 115


# ─── TESTS: TRANSFORM COMPARACIONES ─────────────────────────────────────────

def test_comparaciones_rechaza_nulos(sample_comparaciones):
    valid, rejected = transform_comparaciones(sample_comparaciones)
    assert rejected["motivo_rechazo"].str.contains("nulo").any()


def test_comparaciones_rechaza_fuera_de_rango(sample_comparaciones):
    valid, rejected = transform_comparaciones(sample_comparaciones)
    assert rejected["motivo_rechazo"].str.contains("fuera de rango").any()


def test_comparaciones_solo_validos_en_valid(sample_comparaciones):
    valid, _ = transform_comparaciones(sample_comparaciones)
    assert (valid["pokemon_a"].between(1, 150)).all()
    assert (valid["pokemon_b"].between(1, 150)).all()
    assert (valid["nivel_a"].between(1, 100)).all()
    assert (valid["nivel_b"].between(1, 100)).all()


def test_comparaciones_registra_duplicados(sample_comparaciones_con_dupes):
    _, rejected = transform_comparaciones(sample_comparaciones_con_dupes)
    assert (rejected["motivo_rechazo"] == "duplicado exacto").sum() == 1


def test_comparaciones_duplicado_no_llega_a_valid(sample_comparaciones_con_dupes):
    valid, _ = transform_comparaciones(sample_comparaciones_con_dupes)
    assert len(valid) == 2


def test_comparaciones_todos_rechazados_tienen_motivo(sample_comparaciones):
    _, rejected = transform_comparaciones(sample_comparaciones)
    assert rejected["motivo_rechazo"].notna().all()
    assert (rejected["motivo_rechazo"] != "").all()


# ─── TESTS: TRANSFORM POKEMON ────────────────────────────────────────────────

def test_pokemon_agrega_total_stats(sample_pokemon):
    df = transform_pokemon(sample_pokemon)
    pikachu = df[df["name"] == "pikachu"].iloc[0]
    assert pikachu["total_stats"] == 35 + 55 + 40 + 50 + 50 + 90


def test_pokemon_convierte_height_m(sample_pokemon):
    df = transform_pokemon(sample_pokemon)
    pikachu = df[df["name"] == "pikachu"].iloc[0]
    assert pikachu["height_m"] == pytest.approx(0.4)


def test_pokemon_convierte_weight_kg(sample_pokemon):
    df = transform_pokemon(sample_pokemon)
    pikachu = df[df["name"] == "pikachu"].iloc[0]
    assert pikachu["weight_kg"] == pytest.approx(6.0)


def test_pokemon_type2_none_rellena(sample_pokemon):
    df = transform_pokemon(sample_pokemon)
    pikachu = df[df["name"] == "pikachu"].iloc[0]
    assert pikachu["type2"] == "none"


def test_pokemon_stat_role_asignado(sample_pokemon):
    df = transform_pokemon(sample_pokemon)
    assert df["stat_role"].notna().all()
    assert df["stat_role"].isin(["tank", "physical_sweeper", "special_sweeper", "speedster", "balanced"]).all()


# ─── TESTS: ENRICH COMPARACIONES ─────────────────────────────────────────────

@pytest.fixture
def enriched(sample_pokemon):
    comp = pd.DataFrame({
        "pokemon_a": [25], "nivel_a": [50],
        "pokemon_b": [6],  "nivel_b": [75],
    })
    pk = transform_pokemon(sample_pokemon)
    return enrich_comparaciones(comp, pk)


def test_enrich_calcula_stats_al_nivel(enriched):
    row = enriched.iloc[0]
    # HP de pikachu lv50: floor(2*35*50/100) + 50 + 10 = 95
    assert row["a_hp_lv"] == 95


def test_enrich_calcula_total_lv(enriched):
    row = enriched.iloc[0]
    assert row["a_total_lv"] == sum([
        row["a_hp_lv"], row["a_attack_lv"], row["a_defense_lv"],
        row["a_special_attack_lv"], row["a_special_defense_lv"], row["a_speed_lv"]
    ])


def test_enrich_poder_total_es_suma(enriched):
    row = enriched.iloc[0]
    assert row["poder_total"] == row["a_total_lv"] + row["b_total_lv"]


def test_enrich_diferencia_poder_es_absoluta(enriched):
    row = enriched.iloc[0]
    assert row["diferencia_poder"] == abs(row["a_total_lv"] - row["b_total_lv"])


def test_enrich_ganador_correcto(enriched):
    row = enriched.iloc[0]
    if row["a_total_lv"] > row["b_total_lv"]:
        assert row["ganador"] == "pikachu"
    elif row["b_total_lv"] > row["a_total_lv"]:
        assert row["ganador"] == "charizard"
    else:
        assert row["ganador"] == "empate"


def test_enrich_empate_cuando_iguales(sample_pokemon):
    comp = pd.DataFrame({
        "pokemon_a": [25], "nivel_a": [50],
        "pokemon_b": [25], "nivel_b": [50],
    })
    pk = transform_pokemon(sample_pokemon)
    df = enrich_comparaciones(comp, pk)
    assert df.iloc[0]["ganador"] == "empate"


# ─── TESTS: TABLA COMPARACION ─────────────────────────────────────────────────

def test_tabla_comparacion_columnas(enriched):
    df = build_tabla_comparacion(enriched)
    for col in ["pokemon", "rival", "poder", "rival_poder",
                "ganador", "resultado", "poder_total", "diferencia_poder", "ventaja_pct"]:
        assert col in df.columns


def test_tabla_comparacion_resultado_gana(enriched):
    df = build_tabla_comparacion(enriched)
    row = df.iloc[0]
    if row["ganador"] == row["pokemon"]:
        assert row["resultado"] == "gana"
    elif row["ganador"] == row["rival"]:
        assert row["resultado"] == "pierde"
    else:
        assert row["resultado"] == "empate"


def test_tabla_comparacion_filas_igual_que_battles(enriched):
    df = build_tabla_comparacion(enriched)
    assert len(df) == len(enriched)


# ─── TESTS: EDGE CASES ───────────────────────────────────────────────────────

def test_comparaciones_dataframe_vacio():
    empty = pd.DataFrame(columns=["pokemon_a", "nivel_a", "pokemon_b", "nivel_b"])
    valid, rejected = transform_comparaciones(empty)
    assert len(valid) == 0
    assert len(rejected) == 0


def test_comparaciones_todos_invalidos():
    df = pd.DataFrame({
        "pokemon_a": ["0",   "-1",  "999"],
        "nivel_a":   ["0",   "101", "50"],
        "pokemon_b": ["151", "200", "1"],
        "nivel_b":   ["50",  "50",  "50"],
    })
    valid, rejected = transform_comparaciones(df)
    assert len(valid) == 0
    assert len(rejected) == 3
