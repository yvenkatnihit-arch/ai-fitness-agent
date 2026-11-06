"""Indian dishes computed from our own recipes (D-037): raw ingredient grams + the cooked weight.

    per 100 g cooked = sum(ingredient per 100 g x raw grams / 100) x 100 / cooked weight

Cooking mostly changes WATER (rice absorbs it, halwa loses it); protein, carbs and fat stay.
So the cooked weight carries the effect of boiling, steaming or reducing. For frying, the
recipe lists the oil the food absorbs, not the oil left in the pan.

data/recipes.csv       one row per dish (key, name, category, cooked_g, reviewed_by, note)
data/recipe_items.csv  one row per ingredient (recipe, ingredient, raw_g, note); ingredient is
                       a key from ingredients.csv that passed validation
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from fooddata.checks import DIET_ORDER, Issue, check_diet_class, check_dish_plausibility, check_food
from fooddata.download import DATA_DIR
from fooddata.records import FoodRecord
from fooddata.review import Reviewed

RECIPES = DATA_DIR / "recipes.csv"
RECIPE_ITEMS = DATA_DIR / "recipe_items.csv"
RECIPE_COLUMNS = ["key", "name", "local_names", "category", "cooked_g", "reviewed_by", "note"]
ITEM_COLUMNS = ["recipe", "ingredient", "raw_g", "note"]

YIELD_RANGE = (0.5, 3.0)       # cooked weight / raw weight; outside this, re-check the cooked weight
FIBRE_UNKNOWN_LIMIT = 0.05     # fibre is "unknown" if ingredients without fibre data are > 5 % of the weight
NUTRIENTS = ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")


@dataclass(frozen=True)
class Ingredient:
    """One validated food, per 100 g, with carbs already converted to available carbs (D-038)."""
    key: str
    diet_class: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    carbs_quality: str = "exact"

    @classmethod
    def from_reviewed(cls, r: Reviewed) -> "Ingredient":
        f = r.food
        return cls(r.row["key"], r.row["diet_class"], f.kcal, f.protein_g, r.carbs_g, f.fat_g, f.fiber_g,
                   r.carbs_quality or "exact")


def per_100g_cooked(parts: list[tuple[Ingredient, float]], cooked_g: float) -> dict[str, float | None]:
    """Sum each nutrient over the raw grams, then scale to 100 g of the cooked dish."""
    raw_total = sum(grams for _, grams in parts)
    result: dict[str, float | None] = {}
    for nutrient in NUTRIENTS:
        known = [(getattr(i, nutrient), g) for i, g in parts if getattr(i, nutrient) is not None]
        unknown_g = raw_total - sum(g for _, g in known)
        if nutrient == "fiber_g" and unknown_g > FIBRE_UNKNOWN_LIMIT * raw_total:
            result[nutrient] = None  # too much is unmeasured: unknown, never undercounted
            continue
        total = sum(value * g / 100 for value, g in known)
        result[nutrient] = round(total * 100 / cooked_g, 2)
    return result


def strictest_diet(classes: list[str]) -> str:
    """A dish is only as vegetarian as its least vegetarian ingredient."""
    return max(classes, key=DIET_ORDER.index)


def _positive(value: str) -> float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    return number if number > 0 else None


def review_recipe(recipe: dict, items: list[dict], ingredients: dict[str, Ingredient]) -> Reviewed:
    row = {**recipe, "diet_class": "", "match": "recipe"}
    result = Reviewed(row)
    cooked_g = _positive(recipe["cooked_g"])
    if cooked_g is None:
        result.add(Issue("recipe", "error", f"cooked_g must be a positive number, got {recipe['cooked_g']!r}"))
    if not items:
        result.add(Issue("recipe", "error", "recipe has no ingredients"))
    parts: list[tuple[Ingredient, float]] = []
    for item in items:
        grams = _positive(item["raw_g"])
        ingredient = ingredients.get(item["ingredient"])
        if ingredient is None:
            result.add(Issue("recipe", "error", f"{item['ingredient']!r} is not a validated ingredient"))
        if grams is None:
            result.add(Issue("recipe", "error", f"{item['ingredient']}: raw_g must be positive, got {item['raw_g']!r}"))
        if ingredient and grams:
            parts.append((ingredient, grams))
    if result.issues:
        result.status = "blocked"
        return result

    values = per_100g_cooked(parts, cooked_g)
    diet = strictest_diet([i.diet_class for i, _ in parts])
    row["diet_class"] = diet
    raw_total = sum(g for _, g in parts)
    recipe_text = " + ".join(f"{g:g} g {i.key}" for i, g in parts) + f" -> {cooked_g:g} g cooked"
    row["note"] = "; ".join(filter(None, [recipe_text, recipe["note"]]))

    food = FoodRecord(source="computed", source_id=recipe["key"], name=f"Recipe: {recipe['name']}",
                      category=recipe["category"], carb_basis="available", **values)
    result.food = food
    result.carbs_g = values["carbs_g"]
    result.carbs_quality = "approximate" if any(i.carbs_quality != "exact" for i, _ in parts) else "exact"

    result.add(*check_food(food))
    result.add(*check_dish_plausibility(recipe["category"], food.kcal))
    # Diet comes from the ingredients; our name must not promise something else (e.g. "paneer" but no dairy).
    result.add(*check_diet_class(f"{recipe['name']} {recipe['local_names']}", None, diet))
    ratio = cooked_g / raw_total
    if not YIELD_RANGE[0] <= ratio <= YIELD_RANGE[1]:
        result.add(Issue("yield", "warning", f"cooked weight is {ratio:.2f}x the raw weight; check cooked_g"))
    if food.fiber_g is None:
        result.add(Issue("fibre", "warning", "fibre unknown: ingredients without fibre data are over 5 % of the weight"))

    if any(i.severity == "error" for i in result.issues):
        result.status = "blocked"
    elif result.issues or not recipe["reviewed_by"].strip():
        result.status = "review"  # every recipe needs a human sign-off before it's "ready"
    return result


def review_recipes(recipes: list[dict], items: list[dict], usable: dict[str, Reviewed]) -> list[Reviewed]:
    ingredients = {key: Ingredient.from_reviewed(r) for key, r in usable.items()}
    by_recipe: dict[str, list[dict]] = {}
    for item in items:
        by_recipe.setdefault(item["recipe"], []).append(item)
    unknown = sorted(set(by_recipe) - {r["key"] for r in recipes})
    if unknown:
        raise ValueError(f"recipe_items.csv mentions recipes that don't exist: {unknown}")
    return [review_recipe(r, by_recipe.get(r["key"], []), ingredients) for r in recipes]


def _read(path: Path, columns: list[str]) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != columns:
            raise ValueError(f"{path.name} columns are {reader.fieldnames}, expected {columns}")
        return list(reader)


def read_recipes(recipes_path: Path = RECIPES, items_path: Path = RECIPE_ITEMS) -> tuple[list[dict], list[dict]]:
    recipes = _read(recipes_path, RECIPE_COLUMNS)
    keys = [r["key"] for r in recipes]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise ValueError(f"duplicate keys in {recipes_path.name}: {duplicates}")
    return recipes, _read(items_path, ITEM_COLUMNS)
