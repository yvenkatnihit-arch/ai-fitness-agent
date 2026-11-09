"""The meal plan as a proposal payload: build it, verify it independently, hide numbers when required (Step 6.7d, D-067).

`verify_payload` does NOT trust the saved JSON. It recomputes every item's nutrition from the foods table, checks the
day totals against the user's calorie band and protein cap, and checks diet, dislikes and household units. It runs
when the plan is generated and again when the user approves it.
"""

import copy
from collections.abc import Collection, Mapping
from datetime import date
from typing import TYPE_CHECKING, Any

from app.calc.meal_pool import ALL_SLOTS, ALLOWED_DIET_CLASSES, SLOTS, PoolFood, disliked
from app.calc.meal_solver import DayTargets
from app.calc.portions import Per100g, nutrition_for

if TYPE_CHECKING:
    from app.workflows.pick_meals import WeekPlan

PAYLOAD_VERSION = 1
HOUSEHOLD_UNITS = frozenset({"katori", "piece", "cup", "glass", "bowl", "plate", "slice", "tbsp", "tsp", "handful"})
NUTRITION_KEYS = ("kcal", "protein_g", "carbs_g", "fat_g")
MAX_ITEM_GRAMS = 2000          # meal_plan_items.grams check
NUMBER_TOLERANCE = 0.15        # payload numbers must match our recomputation (both round to 0.1)
TOTAL_TOLERANCE = 1.5          # kcal and grams of protein: per-item rounding
UNIT_GRAMS_TOLERANCE = 0.2


def build_payload(week: "WeekPlan", targets: DayTargets, *, diet_type: str, goal: str, week_start: date,
                  numbers_hidden: bool) -> dict[str, Any]:
    days = []
    for plan in week.days:
        position: dict[str, int] = {}
        items = []
        for it in plan.solution.items:
            position[it.slot] = position.get(it.slot, 0) + 1
            items.append({
                "slot": it.slot, "role": it.role, "position": position[it.slot], "food_key": it.food_key,
                "name": it.food_name, "grams": it.portion.grams, "unit": it.portion.unit,
                "quantity": it.portion.quantity, "text": it.portion.text, "kcal": it.nutrition.kcal,
                "protein_g": it.nutrition.protein_g, "carbs_g": it.nutrition.carbs_g, "fat_g": it.nutrition.fat_g,
            })
        t = plan.solution.totals
        days.append({
            "day_of_week": plan.day, "source": plan.source, "status": plan.solution.status,
            "totals": {"kcal": t.kcal, "protein_g": t.protein_g, "carbs_g": t.carbs_g, "fat_g": t.fat_g},
            "percent_of_target": {k: round(v, 1) for k, v in plan.solution.percent_of_target.items()},
            "issues": list(plan.solution.issues), "items": items,
        })
    return {
        "kind": "meal_plan", "version": PAYLOAD_VERSION, "week_start": week_start.isoformat(), "diet_type": diet_type,
        "goal": goal, "emphasis": week.emphasis, "slots": list(week.slots), "portion_scale": week.portion_scale,
        "numbers_hidden": numbers_hidden,
        "targets": {"kcal": round(targets.kcal), "protein_g": round(targets.protein_g), "carbs_g": round(targets.carbs_g),
                    "fat_g": round(targets.fat_g)},
        "thin_roles": {s: list(r) for s, r in week.thin_roles.items()},
        "days": days,
    }


def summarize(payload: Mapping[str, Any]) -> str:
    """One line for the proposal card (the database allows 500 characters). No numbers when they must be hidden."""
    diet = payload["diet_type"].replace("_", " ")
    meals = len(payload["slots"])
    if payload.get("numbers_hidden"):
        return f"7-day {diet} meal plan with balanced meals, {meals} meals a day, starting {payload['week_start']}."
    return (f"7-day {diet} meal plan, {meals} meals a day, about {payload['targets']['kcal']} kcal a day, "
            f"starting {payload['week_start']}.")


def hide_numbers(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A copy with every calorie and macro number removed. Applied by the SERVER to anything sent to a user whose plan
    must not show numbers (eating-disorder history, brief section 7), so no screen can leak them."""
    out = copy.deepcopy(dict(payload))
    for key in ("targets", "emphasis", "portion_scale"):      # all derived from the calorie and protein numbers
        out.pop(key, None)
    for day in out.get("days", []):
        for key in ("totals", "percent_of_target", "issues", "status"):   # "status" says whether the numbers hit the targets
            day.pop(key, None)
        for item in day.get("items", []):
            for key in NUTRITION_KEYS:
                item.pop(key, None)
    return out


def verify_payload(payload: object, foods: Mapping[str, PoolFood], *, diet_type: str, dislikes: Collection[str],
                   targets: DayTargets) -> list[str]:
    """Everything wrong with a meal plan, in plain words; empty means it is safe to save and to apply."""
    if not isinstance(payload, dict) or payload.get("kind") != "meal_plan":
        return ["not a meal plan"]
    days = payload.get("days")
    if not isinstance(days, list) or [d.get("day_of_week") if isinstance(d, dict) else None for d in days] != list(range(1, 8)):
        return ["a plan needs exactly seven days, in order"]
    slots = payload.get("slots")
    if slots not in (list(SLOTS), list(ALL_SLOTS)):
        return ["the meals of a day are not a known set"]
    if diet_type not in ALLOWED_DIET_CLASSES:
        return [f"unknown diet type {diet_type!r}"]
    allowed_classes = ALLOWED_DIET_CLASSES[diet_type]
    problems: list[str] = []
    for day in days:
        label = f"day {day['day_of_week']}"
        items = day.get("items")
        if not isinstance(items, list) or not items:
            problems.append(f"{label}: no meals")
            continue
        seen_slots = {i.get("slot") for i in items if isinstance(i, dict)}
        if seen_slots != set(slots):
            problems.append(f"{label}: the meals do not match {slots}")
        positions: dict[str, list[int]] = {}
        kcal = protein = 0.0
        for n, item in enumerate(items, 1):
            where = f"{label} item {n}"
            if not isinstance(item, dict):
                problems.append(f"{where}: not an item")
                continue
            food = foods.get(item.get("food_key"))
            if food is None:
                problems.append(f"{where}: not in the food database")
                continue
            if food.diet_class not in allowed_classes:
                problems.append(f"{where}: {food.name} is not allowed for a {diet_type.replace('_', ' ')} diet")
            if disliked(food, dislikes):
                problems.append(f"{where}: {food.name} is on the disliked list")
            grams = item.get("grams")
            if not isinstance(grams, (int, float)) or isinstance(grams, bool) or not 0 < grams <= MAX_ITEM_GRAMS:
                problems.append(f"{where}: grams must be above 0 and at most {MAX_ITEM_GRAMS}")
                continue
            unit, qty = item.get("unit"), item.get("quantity")
            if (unit is None) != (qty is None):
                problems.append(f"{where}: unit and quantity go together")
            elif unit is not None:
                unit_g = dict(food.units).get(unit)
                if unit not in HOUSEHOLD_UNITS or unit_g is None:
                    problems.append(f"{where}: {food.name} is not measured in '{unit}'")
                elif not isinstance(qty, (int, float)) or isinstance(qty, bool) or qty <= 0 or abs(qty * unit_g - grams) > UNIT_GRAMS_TOLERANCE:
                    problems.append(f"{where}: {qty} {unit} does not match {grams} g")
            positions.setdefault(item.get("slot"), []).append(item.get("position"))
            truth = nutrition_for(float(grams), Per100g(food.kcal, food.protein_g, food.carbs_g, food.fat_g))
            for key in NUTRITION_KEYS:
                if not isinstance(item.get(key), (int, float)) or abs(item[key] - getattr(truth, key)) > NUMBER_TOLERANCE:
                    problems.append(f"{where}: the {key.replace('_g', '')} numbers do not match the food data")
                    break
            kcal += truth.kcal
            protein += truth.protein_g
        for slot, order in positions.items():
            if order != list(range(1, len(order) + 1)):
                problems.append(f"{label} {slot}: wrong order of items")
        if not targets.kcal_min - TOTAL_TOLERANCE <= kcal <= targets.kcal_max + TOTAL_TOLERANCE:
            problems.append(f"{label}: {kcal:.0f} kcal is outside the safe range {targets.kcal_min:.0f} to {targets.kcal_max:.0f}")
        if protein > targets.protein_max_g + TOTAL_TOLERANCE:
            problems.append(f"{label}: {protein:.0f} g of protein is above the {targets.protein_max_g:.0f} g limit")
    return problems
