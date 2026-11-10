"""What GET /plans/meal/active returns. Numbers are removed HERE (the server) for users who must not see them."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from app.calc.meal_plan_payload import portion_text
from app.calc.meal_pool import ALL_SLOTS


class MealItemOut(BaseModel):
    position: int
    name: str
    grams: float
    text: str                       # "1.5 katori (225 g)"
    kcal: float | None = None       # None when the user must not see numbers
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None


class MealOut(BaseModel):
    slot: str
    items: list[MealItemOut]


class MealDayOut(BaseModel):
    day_of_week: int                # 1 = Monday
    meals: list[MealOut]
    totals: dict[str, float] | None = None


class ActiveMealPlanOut(BaseModel):
    id: str
    week_start: date
    version: int
    approved_at: datetime
    numbers_hidden: bool
    targets: dict[str, float] | None = None
    days: list[MealDayOut]
    how_made: dict[str, Any] | None = None


def to_active_meal_plan(raw: dict) -> ActiveMealPlanOut:
    plan_id, week_start, version, approved_at = raw["plan"]
    t = raw["targets"]
    hidden = bool(t[4]) if t else False
    by_day: dict[int, dict[str, list[MealItemOut]]] = {}
    sums: dict[int, dict[str, float]] = {}
    for dow, slot, position, name, grams, unit, qty, kcal, protein, carbs, fat in raw["items"]:
        item = MealItemOut(position=position, name=name, grams=float(grams),
                           text=portion_text(float(grams), unit, float(qty) if qty is not None else None))
        if not hidden:
            item.kcal, item.protein_g, item.carbs_g, item.fat_g = float(kcal), float(protein), float(carbs), float(fat)
            s = sums.setdefault(dow, {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0})
            s["kcal"] += float(kcal)
            s["protein_g"] += float(protein)
            s["carbs_g"] += float(carbs)
            s["fat_g"] += float(fat)
        by_day.setdefault(dow, {}).setdefault(slot, []).append(item)
    days = [
        MealDayOut(
            day_of_week=dow,
            meals=[MealOut(slot=s, items=sorted(by_day[dow][s], key=lambda i: i.position)) for s in ALL_SLOTS if s in by_day[dow]],
            totals={k: round(v, 1) for k, v in sums[dow].items()} if dow in sums else None,
        )
        for dow in sorted(by_day)
    ]
    targets = None if hidden or not t else {"kcal": round(float(t[0])), "protein_g": round(float(t[1])),
                                              "carbs_g": round(float(t[2])), "fat_g": round(float(t[3]))}
    made = raw["how_made"]
    if hidden and made:
        for key in ("days_ok", "days_with_issues", "average_percent_of_target", "emphasis", "portion_scale", "protein_shortfall"):
            made.pop(key, None)
    return ActiveMealPlanOut(id=str(plan_id), week_start=week_start, version=version, approved_at=approved_at,
                             numbers_hidden=hidden, targets=targets, days=days, how_made=made)
