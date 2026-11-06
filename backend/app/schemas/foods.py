"""What food search returns. Values are per 100 g; units say how many grams one household measure is."""

from pydantic import BaseModel


class FoodUnitOut(BaseModel):
    unit: str     # katori, piece, glass, tsp, tbsp, slice, ...
    grams: float


class FoodOut(BaseModel):
    id: int
    key: str
    name: str
    local_names: list[str]
    category: str | None
    diet_class: str
    is_dish: bool
    kcal_per_100g: float
    protein_g_per_100g: float
    carbs_g_per_100g: float   # available carbohydrate, fibre excluded (D-038)
    fat_g_per_100g: float
    fiber_g_per_100g: float | None  # None = not measured in the source (never shown as 0)
    verified: bool            # False = values still in review (data/reports/ingredients_review.md)
    units: list[FoodUnitOut]


def to_food_out(row: dict) -> FoodOut:
    fiber = row["fiber_g"]
    return FoodOut(
        id=row["id"], key=row["key"], name=row["name"], local_names=list(row["synonyms"]),
        category=row["category"], diet_class=row["diet_class"], is_dish=row["is_dish"],
        kcal_per_100g=float(row["kcal"]), protein_g_per_100g=float(row["protein_g"]),
        carbs_g_per_100g=float(row["carbs_g"]), fat_g_per_100g=float(row["fat_g"]),
        fiber_g_per_100g=None if fiber is None else float(fiber),
        verified=row["review_status"] == "ready",
        units=[FoodUnitOut(**u) for u in row["units"]],
    )
