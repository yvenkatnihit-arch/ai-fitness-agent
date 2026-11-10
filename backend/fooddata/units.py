"""Household units: how many grams is "1 katori dal", "1 roti", "1 tsp oil" (Step 4.5b, D-040).

data/food_units.csv says HOW each unit's grams are known, and this module checks it:

  method usda    grams = a measured USDA SR Legacy portion. `ref` is the USDA fdc_id ("self" = the
                 food's own USDA id), `ref_portion` + `ref_grams` must match a row in USDA's
                 food_portion.csv exactly (checked), e.g. 1 large egg = 50 g.
  method volume  katori / glass: our standard volume x a density from a measured USDA cup
                 weight, e.g. dal katori = 150 ml x (241 g / 236.6 ml) = 152.8 g.
  method recipe  the piece size our recipe defines (idli: 720 g cooked / 18 idlis = 40 g).

Writes data/food_units_validated.csv (key, unit, grams, source) for the loader.
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from fooddata.download import DATA_DIR, MANIFEST, RAW_DIR
from fooddata.recipes import RECIPES
from fooddata.usda import read_portions

UNITS_FILE = DATA_DIR / "food_units.csv"
UNITS_VALIDATED = DATA_DIR / "food_units_validated.csv"
COLUMNS = ["key", "unit", "method", "ref", "ref_portion", "ref_grams", "note"]

# Standard volumes (D-040). Home katoris and glasses vary; change these in one place if needed.
VOLUME_ML = {"katori": 150, "glass": 250, "bowl": 300, "cup": 240}   # bowl (a soup or salad bowl) and cup: defaults for Venkat to confirm (D-089)
US_CUP_ML = 236.6  # USDA "cup" portions are US cups
# Must match the check constraint on public.food_units.unit
DB_UNITS = {"katori", "piece", "cup", "glass", "bowl", "plate", "slice", "tbsp", "tsp", "handful"}
MAX_GRAMS = 2000


@dataclass(frozen=True)
class Unit:
    key: str
    unit: str
    grams: float
    source: str


def portion_matches(usda_text: str, ref_portion: str) -> bool:
    """'1 medium' matches USDA '1 medium' and '1 medium (7" to 7-7/8" long)', not '1 medium slice'."""
    return usda_text == ref_portion or usda_text.startswith(ref_portion + " (")


def cup_amount(ref_portion: str) -> float:
    """'1 cup' -> 1.0, '0.5 cup (8 fl oz)' -> 0.5. Volume units need a cup-based density."""
    amount, _, rest = ref_portion.partition(" ")
    if not rest.startswith("cup"):
        raise ValueError(f"volume units need a USDA cup portion, got {ref_portion!r}")
    return float(amount)


def check_unit(row: dict, food_sources: dict[str, tuple[str, str]], portions: dict[str, list[tuple[str, float]]],
               recipe_keys: set[str]) -> Unit:
    """One CSV row -> a validated Unit, or ValueError saying exactly what is wrong."""
    key, unit, method = row["key"], row["unit"], row["method"]
    where = f"{key} / {unit}"
    if key not in food_sources:
        raise ValueError(f"{where}: {key!r} is not a validated food")
    if unit not in DB_UNITS:
        raise ValueError(f"{where}: unknown unit (allowed: {sorted(DB_UNITS)})")
    try:
        ref_grams = float(row["ref_grams"])
    except ValueError:
        raise ValueError(f"{where}: ref_grams is not a number ({row['ref_grams']!r})") from None

    if method == "recipe":
        if row["ref"] not in recipe_keys:
            raise ValueError(f"{where}: recipe {row['ref']!r} not found in recipes.csv")
        grams, source = ref_grams, f"our recipe '{row['ref']}': {row['ref_portion']} = {ref_grams:g} g"
    elif method in ("usda", "volume"):
        fdc_id = row["ref"]
        if fdc_id == "self":
            source_name, source_id = food_sources[key]
            if source_name != "usda_sr_legacy":
                raise ValueError(f"{where}: ref 'self' needs a USDA food, but {key} is from {source_name}")
            fdc_id = source_id
        measured = [g for text, g in portions.get(fdc_id, []) if portion_matches(text, row["ref_portion"])]
        if ref_grams not in measured:
            found = ", ".join(f"{t} = {g:g} g" for t, g in portions.get(fdc_id, [])) or "no portions"
            raise ValueError(f"{where}: USDA {fdc_id} has no portion '{row['ref_portion']}' = {ref_grams:g} g ({found})")
        usda = f"USDA SR Legacy {fdc_id}: {row['ref_portion']} = {ref_grams:g} g"
        if method == "usda":
            if unit in VOLUME_ML:
                raise ValueError(f"{where}: {unit} is a volume unit; use method 'volume'")
            grams, source = ref_grams, usda
        else:
            if unit not in VOLUME_ML:
                raise ValueError(f"{where}: method 'volume' is only for {sorted(VOLUME_ML)}")
            density = ref_grams / (cup_amount(row["ref_portion"]) * US_CUP_ML)  # g per ml
            grams = round(VOLUME_ML[unit] * density, 1)
            source = f"{unit} {VOLUME_ML[unit]} ml x density from {usda}"
    else:
        raise ValueError(f"{where}: unknown method {method!r} (usda, volume, recipe)")

    if not 0 < grams <= MAX_GRAMS:
        raise ValueError(f"{where}: {grams} g is outside 0-{MAX_GRAMS}")
    return Unit(key, unit, grams, source)


def build_units(food_sources: dict[str, tuple[str, str]], portions: dict[str, list[tuple[str, float]]],
                recipe_keys: set[str], rows: list[dict]) -> tuple[list[Unit], list[str]]:
    """Validate every row. Returns (units, errors); a row with an error is left out."""
    units, errors, seen = [], [], set()
    for row in rows:
        if (row["key"], row["unit"]) in seen:
            errors.append(f"{row['key']} / {row['unit']}: listed twice")
            continue
        seen.add((row["key"], row["unit"]))
        try:
            units.append(check_unit(row, food_sources, portions, recipe_keys))
        except ValueError as error:
            errors.append(str(error))
    return units, errors


def read_unit_rows(path: Path = UNITS_FILE) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"{path.name} columns are {reader.fieldnames}, expected {COLUMNS}")
        return list(reader)


def usda_portions() -> dict[str, list[tuple[str, float]]]:
    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]
    usda_file = next(RAW_DIR / s["file"] for s in sources if s["key"] == "usda_sr_legacy")
    return read_portions(usda_file)


def write_units(units: list[Unit], path: Path = UNITS_VALIDATED) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "unit", "grams", "source"])
        for u in units:
            writer.writerow([u.key, u.unit, u.grams, u.source])


def recipe_keys(path: Path = RECIPES) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["key"] for row in csv.DictReader(handle)}
