"""
Pokemon Pipeline — Generador de datos sintéticos de comparación
Genera comparacion.csv con suciedad intencional: nulos, valores fuera de rango y duplicados
Genera pokemon.json con stats base desde la PokeAPI (fuente oficial, sin suciedad)
"""

import json
import os
import random
import time

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

random.seed(29)
np.random.seed(29)

BASE_URL = "https://pokeapi.co/api/v2"

POKEMON_MIN = 1
POKEMON_MAX = 150
NIVEL_MIN   = 1
NIVEL_MAX   = 100


# ─── POKEMON (PokeAPI) ───────────────────────────────────────────────────────

def _get(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise e


def _fetch_pokemon(pokemon_id: int) -> dict:
    data   = _get(f"{BASE_URL}/pokemon/{pokemon_id}")
    stats  = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
    effort = {s["stat"]["name"]: s["effort"]    for s in data["stats"]}
    types  = [t["type"]["name"] for t in data["types"]]
    return {
        "id":                     data["id"],
        "name":                   data["name"],
        "type1":                  types[0] if len(types) > 0 else None,
        "type2":                  types[1] if len(types) > 1 else None,
        "hp":                     stats.get("hp"),
        "attack":                 stats.get("attack"),
        "defense":                stats.get("defense"),
        "special_attack":         stats.get("special-attack"),
        "special_defense":        stats.get("special-defense"),
        "speed":                  stats.get("speed"),
        "effort_hp":              effort.get("hp"),
        "effort_attack":          effort.get("attack"),
        "effort_defense":         effort.get("defense"),
        "effort_special_attack":  effort.get("special-attack"),
        "effort_special_defense": effort.get("special-defense"),
        "effort_speed":           effort.get("speed"),
        "height":                 data["height"],
        "weight":                 data["weight"],
        "base_experience":        data.get("base_experience"),
    }


def generate_pokemon(n=150):
    rows = []
    for pokemon_id in tqdm(range(1, n + 1), desc="Pokemon"):
        rows.append(_fetch_pokemon(pokemon_id))
        time.sleep(0.1)
    return rows


# ─── COMPARACIONES ───────────────────────────────────────────────────────────

def generate_comparaciones(n=500):
    comparaciones = []

    for _ in range(n):
        # ~3% pokemon_a nulo
        pokemon_a = random.randint(POKEMON_MIN, POKEMON_MAX) if random.random() > 0.03 else None
        # ~3% pokemon_b nulo
        pokemon_b = random.randint(POKEMON_MIN, POKEMON_MAX) if random.random() > 0.03 else None
        # ~2% nivel_a nulo
        nivel_a = random.randint(NIVEL_MIN, NIVEL_MAX) if random.random() > 0.02 else None
        # ~2% nivel_b nulo
        nivel_b = random.randint(NIVEL_MIN, NIVEL_MAX) if random.random() > 0.02 else None

        # Suciedad intencional: ~5% pokemon fuera de rango (0, negativos, >150)
        if pokemon_a is not None and random.random() < 0.05:
            pokemon_a = random.choice([0, -1, 151, 200, 999])
        if pokemon_b is not None and random.random() < 0.05:
            pokemon_b = random.choice([0, -1, 151, 200, 999])

        # Suciedad intencional: ~4% nivel fuera de rango (0, negativos, >100)
        if nivel_a is not None and random.random() < 0.04:
            nivel_a = random.choice([0, -1, 101, 150])
        if nivel_b is not None and random.random() < 0.04:
            nivel_b = random.choice([0, -1, 101, 150])

        comparaciones.append({
            "pokemon_a": pokemon_a,
            "nivel_a":   nivel_a,
            "pokemon_b": pokemon_b,
            "nivel_b":   nivel_b,
        })

    # Duplicados exactos (~2%)
    dupes = random.sample(comparaciones, k=10)
    comparaciones.extend(dupes)

    return comparaciones


# ─── GUARDAR ─────────────────────────────────────────────────────────────────

def save_all():
    print("Generando pokemon.json (PokeAPI) ...")
    pokemon = generate_pokemon(150)
    with open("data/raw/pokemon.json", "w", encoding="utf-8") as f:
        json.dump(pokemon, f, ensure_ascii=False, indent=2)
    print(f"   {len(pokemon)} Pokemon guardados")

    print("Generando comparacion.csv ...")
    comparaciones = generate_comparaciones(500)
    df_comp = pd.DataFrame(comparaciones)
    df_comp.to_csv("data/raw/comparacion.csv", index=False)
    print(f"   {len(df_comp)} registros (incluye duplicados y suciedad)")

    print("\nArchivos generados en data/raw/")
    print("   - pokemon.json")
    print("   - comparacion.csv")

    return pokemon, comparaciones


if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    save_all()
