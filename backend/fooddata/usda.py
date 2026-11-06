"""Read USDA FoodData Central SR Legacy (CSV zip) into FoodRecords.

The zip has three linked tables: food.csv (one row per food), nutrient.csv (what each
nutrient id means) and food_nutrient.csv (one row per food x nutrient). We look nutrients
up by NAME and UNIT, not by hard-coded id, and refuse to continue if one is missing.
"""

import csv
import io
import zipfile
from collections import defaultdict
from pathlib import Path

from fooddata.records import FoodRecord

SOURCE_KEY = "usda_sr_legacy"

# Our field -> (USDA nutrient name, unit).
WANTED = {
    "kcal": ("Energy", "KCAL"),
    "protein_g": ("Protein", "G"),
    "fat_g": ("Total lipid (fat)", "G"),
    "carbs_g": ("Carbohydrate, by difference", "G"),
    "fiber_g": ("Fiber, total dietary", "G"),
    "alcohol_g": ("Alcohol, ethyl", "G"),
}


def _table(archive: zipfile.ZipFile, name: str) -> list[dict]:
    member = next(n for n in archive.namelist() if n == name or n.endswith("/" + name))
    with archive.open(member) as raw:
        return list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")))


def read_sr_legacy(path: Path) -> list[FoodRecord]:
    with zipfile.ZipFile(path) as archive:
        nutrients = _table(archive, "nutrient.csv")
        categories = {row["id"]: row["description"] for row in _table(archive, "food_category.csv")}
        foods = _table(archive, "food.csv")
        food_nutrients = _table(archive, "food_nutrient.csv")

    ids = {}
    for field, (name, unit) in WANTED.items():
        match = [n["id"] for n in nutrients if n["name"] == name and n["unit_name"].upper() == unit]
        if len(match) != 1:
            raise ValueError(f"USDA nutrient {name!r} ({unit}) found {len(match)} times, expected once")
        ids[match[0]] = field

    values: dict[str, dict[str, float]] = defaultdict(dict)
    for row in food_nutrients:
        field = ids.get(row["nutrient_id"])
        if field and row["amount"] not in ("", None):
            values[row["fdc_id"]][field] = float(row["amount"])

    return [
        FoodRecord(
            source=SOURCE_KEY,
            source_id=food["fdc_id"],
            name=food["description"],
            category=categories.get(food["food_category_id"]),
            carb_basis="by_difference",
            **{field: values[food["fdc_id"]].get(field) for field in WANTED},
        )
        for food in foods
    ]
