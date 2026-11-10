"""Protein reached by meal plans on the REAL validated foods (Step 7.10d-3, D-093). Offline: code fallback picks, no model, no database.
Used by scripts/protein_report.py (a printed table) and by tests/test_protein_regression.py (a gate that these numbers do not drop)."""

import csv
from dataclasses import dataclass

from app.calc.engine import calculate_targets
from app.calc.meal_pool import PoolFood
from app.calc.meal_solver import day_targets
from app.calc.meal_week import emphasis_for
from app.llm.client import LLMBusy
from app.workflows.pick_meals import MealPlanFailed, PoolTooSmall, pick_meals
from evals.meal_cases import FAT_LOSS_F, MUSCLE_M
from fooddata.build import VALIDATED
from fooddata.units import UNITS_VALIDATED

DIETS = ("vegan", "vegetarian", "eggetarian", "non_vegetarian")
USERS = {"fat-loss woman": FAT_LOSS_F, "muscle-gain man": MUSCLE_M}


@dataclass(frozen=True)
class Reached:
    target_kcal: float
    target_protein_g: float
    low: float          # worst day, percent of the protein target
    high: float
    mean: float
    ok_days: int
    distinct_foods: int


def pool_foods() -> list[PoolFood]:
    units: dict[str, list[tuple[str, float]]] = {}
    with UNITS_VALIDATED.open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            units.setdefault(r["key"], []).append((r["unit"], float(r["grams"])))
    with VALIDATED.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [PoolFood(i, r["key"], r["name"], r["category"], r["diet_class"], float(r["kcal"]), float(r["protein_g"]), float(r["carbs_g"]), float(r["fat_g"]),
                     r["status"], (), tuple(units.get(r["key"], [])), tuple(r["cuisines"].split(";"))) for i, r in enumerate(rows, 1)]


def down(prompt: str):
    raise LLMBusy()


def measure_one(foods: list[PoolFood], cuisine: str, who: str, diet: str) -> Reached:
    """One week for one made-up user, one diet and one cuisine. Raises PoolTooSmall or MealPlanFailed when no safe week exists."""
    profile = USERS[who]
    e = calculate_targets(profile)
    t = day_targets(e, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    emphasis = emphasis_for(e.protein_g, e.calorie_target_kcal, profile.screening_flags)
    week = pick_meals(foods, diet, [], t, profile.goal, emphasis, ask=down, cuisines=[cuisine])
    pct = [d.solution.percent_of_target["protein"] for d in week.days]
    keys = [i.food_key for d in week.days for i in d.solution.items]
    return Reached(t.kcal, t.protein_g, min(pct), max(pct), sum(pct) / len(pct), sum(d.solution.status == "ok" for d in week.days), len(set(keys)))


def measure(foods: list[PoolFood], cuisine: str) -> list[tuple[str, str, str]]:
    lines = []
    for who in USERS:
        for diet in DIETS:
            try:
                r = measure_one(foods, cuisine, who, diet)
            except (PoolTooSmall, MealPlanFailed) as error:
                lines.append((who, diet, f"REFUSED: {error}"))
                continue
            lines.append((who, diet, f"target {r.target_kcal:4.0f} kcal / {r.target_protein_g:3.0f} g   protein {r.low:3.0f}-{r.high:3.0f}% (mean {r.mean:3.0f}%)   "
                                     f"ok days {r.ok_days}/7   distinct foods {r.distinct_foods:2d}"))
    return lines
