"""Ranking foods for questions like "which foods are high in protein" (Step 8.3, D-107). Pure Python: the ordering is done HERE, never
by a model. Values are per 100 g, exactly as stored."""

from collections.abc import Sequence
from typing import Literal

from app.calc.meal_pool import ALLOWED_DIET_CLASSES, PoolFood, disliked

SortBy = Literal["most_protein", "least_calories", "most_protein_per_calorie"]
Kind = Literal["any", "dishes", "ingredients", "snacks"]
# What people mean by a snack: fruit, nuts and seeds, dairy, eggs, and the snack and dip dishes.
SNACK_CATEGORIES = frozenset({"fruit", "nut_seed", "dairy", "egg", "dish_snack", "dish_dip"})
MAX_RESULTS = 8
MIN_KCAL_FOR_RATIO = 20.0      # a near-zero-calorie food would otherwise "win" protein per calorie on a rounding error


# Not worth ranking: seasoning, sugar and cooking fat would only add noise to "high protein" or "low calorie". Unlike meal plans, plain meat and fish
# ARE ranked (a non-vegetarian asking for high-protein foods should see them).
UNRANKED_CATEGORIES = frozenset({"spice", "sweetener", "fat_oil"})


def ranking_pool(foods: Sequence[PoolFood], diet_type: str, dislikes: Sequence[str] = (), cuisines: Sequence[str] | None = None) -> list[PoolFood]:
    """The foods a person may be shown: their diet, their dislikes removed, and (when given) their cuisines."""
    if diet_type not in ALLOWED_DIET_CLASSES:
        raise ValueError(f"diet_type must be one of {list(ALLOWED_DIET_CLASSES)}, got {diet_type!r}")
    wanted = None if cuisines is None else set(cuisines)
    return [f for f in foods if f.diet_class in ALLOWED_DIET_CLASSES[diet_type] and f.category not in UNRANKED_CATEGORIES
            and not disliked(f, dislikes) and (wanted is None or wanted & set(f.cuisines))]


def is_dish(food: PoolFood) -> bool:
    return food.category.startswith("dish_")


def rank_foods(foods: Sequence[PoolFood], sort_by: SortBy, kind: Kind = "any", min_protein_g: float | None = None,
               max_kcal: float | None = None, limit: int = 5) -> list[PoolFood]:
    """The best `limit` foods under the filters. Ties are broken by name, so the answer never changes between runs."""
    limit = max(1, min(limit, MAX_RESULTS))
    pool = [f for f in foods
            if (kind == "any" or (kind == "snacks" and f.category in SNACK_CATEGORIES)
                or (kind in ("dishes", "ingredients") and (kind == "dishes") == is_dish(f)))
            and (min_protein_g is None or f.protein_g >= min_protein_g)
            and (max_kcal is None or f.kcal <= max_kcal)]
    if sort_by == "most_protein":
        key = lambda f: (-f.protein_g, f.name)                                              # noqa: E731
    elif sort_by == "least_calories":
        pool = [f for f in pool if f.kcal > 0]
        key = lambda f: (f.kcal, f.name)                                                    # noqa: E731
    else:
        pool = [f for f in pool if f.kcal >= MIN_KCAL_FOR_RATIO]
        key = lambda f: (-(f.protein_g / f.kcal), f.name)                                   # noqa: E731
    return sorted(pool, key=key)[:limit]
