"""Portion maths for meal logging (the LLM never does this).

  grams     = quantity x grams per unit        ("2 roti" -> 2 x 43 g = 86 g; unit "g" -> as typed)
  nutrition = grams x value per 100 g / 100   (86 g roti at 202 kcal/100 g -> 173.7 kcal)
"""

from dataclasses import dataclass

GRAMS = "g"
MAX_ITEM_GRAMS = 3000  # same limit as the meal_log_items.grams check constraint


class PortionError(ValueError):
    """The portion can't be turned into grams (unknown unit for this food, or an impossible amount)."""


@dataclass(frozen=True)
class Per100g:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


@dataclass(frozen=True)
class Nutrition:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


def grams_for(quantity: float, unit: str, unit_grams: dict[str, float]) -> float:
    """Grams for '2 piece' / '1.5 katori' / '120 g'. `unit_grams` is this food's household units."""
    if not quantity > 0:
        raise PortionError("quantity must be more than 0")
    if unit == GRAMS:
        grams = quantity
    elif unit in unit_grams:
        grams = quantity * unit_grams[unit]
    else:
        available = ", ".join([GRAMS, *sorted(unit_grams)])
        raise PortionError(f"this food can't be measured in '{unit}'; use one of: {available}")
    grams = round(grams, 1)
    if not 0 < grams <= MAX_ITEM_GRAMS:
        raise PortionError(f"{grams:g} g is outside 0-{MAX_ITEM_GRAMS} g for one item")
    return grams


def nutrition_for(grams: float, food: Per100g) -> Nutrition:
    factor = grams / 100
    return Nutrition(
        kcal=round(food.kcal * factor, 1),
        protein_g=round(food.protein_g * factor, 1),
        carbs_g=round(food.carbs_g * factor, 1),
        fat_g=round(food.fat_g * factor, 1),
    )


def total(items: list[Nutrition]) -> Nutrition:
    """Sum of already-rounded item values (so totals match what the user sees per item)."""
    return Nutrition(
        kcal=round(sum(i.kcal for i in items), 1),
        protein_g=round(sum(i.protein_g for i in items), 1),
        carbs_g=round(sum(i.carbs_g for i in items), 1),
        fat_g=round(sum(i.fat_g for i in items), 1),
    )
