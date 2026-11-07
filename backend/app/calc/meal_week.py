"""Rules for a week of meals: which picks are acceptable, how often a dish may repeat, and the code fallback
(Step 6.7c, D-066). Plain code. The model only chooses KEYS; everything here decides whether a choice is allowed.

A day's picks look like  {"lunch": {"staple": "roti", "protein": "toor_dal", "vegetable": "palak_sabzi", "side": None}, ...}.
"""

import math
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from app.calc.meal_pool import PoolFood, SlotPool
from app.calc.meal_solver import MealItem

Meal = dict[str, str | None]
DayPicks = dict[str, Meal]

# A dish in these roles may not appear twice in the same day (rice or curd at two meals is normal; dal twice is not).
UNIQUE_IN_DAY = frozenset({"main", "protein", "vegetable"})
# Repeats across the week are capped per group of meals: (slots, role).
WEEK_GROUPS = (
    (("breakfast",), "main"),
    (("lunch", "dinner"), "protein"),
    (("lunch", "dinner"), "vegetable"),
)
MIN_REPEAT_CAP = 2          # a dish may always be used at least twice a week
PROTEIN_RICH_SHARE = 0.25   # a food with this share of its calories from protein is tagged "protein-rich"
HIGH_PROTEIN_DIET_SHARE = 0.25


def food_tags(food: PoolFood) -> tuple[str, ...]:
    """Plain-word tags the model may use instead of raw numbers (code computes them; the model never does maths)."""
    tags = []
    if food.protein_g * 4 / max(food.kcal, 1) >= PROTEIN_RICH_SHARE:
        tags.append("protein-rich")
    if food.kcal < 100:
        tags.append("light")
    elif food.kcal >= 250:
        tags.append("calorie-dense")
    return tuple(tags)


def emphasis_for(protein_g: float, kcal: float, flags: Collection[str]) -> str | None:
    """What the picker should lean towards, decided by code: low protein for the kidney flag, high for a protein-heavy target."""
    if "kidney" in flags:
        return "low_protein"
    if protein_g * 4 / max(kcal, 1) >= HIGH_PROTEIN_DIET_SHARE:
        return "high_protein"
    return None


def allowed_keys(pool: Mapping[str, SlotPool], slot: str, role: str) -> list[str]:
    return [f.key for f in pool[slot].roles.get(role, ())]


def validate_day(picks: object, pool: Mapping[str, SlotPool], slots: Sequence[str]) -> list[str]:
    """Everything wrong with one day's picks, in plain words. Empty means acceptable."""
    if not isinstance(picks, dict):
        return ["a day must be a mapping of meals"]
    problems: list[str] = []
    missing = [s for s in slots if s not in picks]
    extra = [s for s in picks if s not in slots]
    if missing:
        problems.append(f"missing meals: {', '.join(missing)}")
    if extra:
        problems.append(f"unknown meals: {', '.join(map(str, extra))}")
    used: Counter[str] = Counter()
    for slot in slots:
        meal = picks.get(slot)
        if meal is None:
            continue
        if not isinstance(meal, dict):
            problems.append(f"{slot} must be a mapping of roles")
            continue
        roles = pool[slot].roles
        for role in meal:
            if role not in roles:
                problems.append(f"{slot} has no role '{role}'")
        for role in roles:
            key = meal.get(role)
            if key is None or key == "":
                if role in pool[slot].required:
                    problems.append(f"{slot} needs a {role} dish")
                continue
            if not isinstance(key, str) or key not in allowed_keys(pool, slot, role):
                problems.append(f"{slot} {role}: '{key}' is not in the allowed list")
                continue
            if role in UNIQUE_IN_DAY:
                used[key] += 1
    problems += [f"'{key}' is used more than once in the day" for key, n in used.items() if n > 1]
    return problems


def validate_week(days: Sequence[object], pool: Mapping[str, SlotPool], slots: Sequence[str]) -> dict[int, list[str]]:
    """Problems per day (0-based index): each day's own rules plus the weekly repeat cap. Days with no problem are absent."""
    problems = {i: validate_day(d, pool, slots) for i, d in enumerate(days)}
    for group_slots, role in WEEK_GROUPS:
        if not all(s in pool for s in group_slots):
            continue
        union = {k for s in group_slots for k in allowed_keys(pool, s, role)}
        if not union:
            continue
        cap = max(MIN_REPEAT_CAP, math.ceil(len(days) * len(group_slots) / len(union)))
        seen: Counter[str] = Counter()
        for i, day in enumerate(days):
            if not isinstance(day, dict):
                continue
            for s in group_slots:
                meal = day.get(s)
                key = meal.get(role) if isinstance(meal, dict) else None
                if isinstance(key, str) and key in union:
                    seen[key] += 1
                    if seen[key] > cap:
                        problems[i].append(f"'{key}' is used too often this week (at most {cap} times)")
    return {i: p for i, p in problems.items() if p}


def to_items(picks: DayPicks, pool: Mapping[str, SlotPool], slots: Sequence[str]) -> list[MealItem]:
    """Valid picks to solver items. Call only after validate_day found nothing."""
    items = []
    for slot in slots:
        for role, foods in pool[slot].roles.items():
            key = picks[slot].get(role)
            if key:
                items.append(MealItem(slot, role, next(f for f in foods if f.key == key)))
    return items


def _ordered(options: Sequence[PoolFood], emphasis: str | None) -> list[PoolFood]:
    if emphasis not in ("high_protein", "low_protein"):
        return list(options)
    density = lambda f: (f.protein_g / max(f.kcal, 1), f.name)
    ranked = sorted(options, key=density, reverse=emphasis == "high_protein")
    return ranked[: max(3, math.ceil(len(ranked) / 2))]      # lean towards the emphasis but keep some variety


def week_usage(days: Sequence[DayPicks]) -> Counter[tuple[str, str]]:
    """How often each (role, dish) has been used so far, for the dishes that must not be overused."""
    return Counter((role, key) for day in days for meal in day.values() for role, key in meal.items()
                   if key and role in UNIQUE_IN_DAY)


def fallback_day(pool: Mapping[str, SlotPool], slots: Sequence[str], day_index: int, offset: int = 0,
                 emphasis: str | None = None, usage: Mapping[tuple[str, str], int] | None = None) -> DayPicks:
    """A safe, boring day made by code: rotate through each role's options by day, so the week varies. Deterministic.
    `offset` gives the search a different rotation to try when a day does not fit. With `usage` (see week_usage) the
    least-used dish wins, so a thin pool is spread evenly over the week. Roles with no option stay empty."""
    day: DayPicks = {}
    taken: set[str] = set()
    for si, slot in enumerate(slots):
        meal: Meal = {}
        for ri, (role, options) in enumerate(pool[slot].roles.items()):
            ordered = _ordered(options, emphasis)
            if not ordered:
                meal[role] = None
                continue
            start = day_index * 3 + si * 2 + ri + offset
            choice = None
            best_use = None
            for step in range(len(ordered)):
                candidate = ordered[(start + step) % len(ordered)].key
                if role in UNIQUE_IN_DAY and candidate in taken:
                    continue
                use = usage.get((role, candidate), 0) if usage else 0
                if best_use is None or use < best_use:       # strictly less: ties keep the rotation order
                    choice, best_use = candidate, use
            meal[role] = choice
            if choice and role in UNIQUE_IN_DAY:
                taken.add(choice)
        day[slot] = meal
    return day


def describe_day(picks: Mapping[str, Any]) -> str:
    """One line for logs and the repair prompt."""
    return "; ".join(f"{slot}: " + ", ".join(f"{k}" for k in meal.values() if k) for slot, meal in picks.items())
