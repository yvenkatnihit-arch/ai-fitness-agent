"""How much of a food can be put in a meal plan, in household steps (Step 6.7b, D-065). Plain code.

A portion is a whole number of STEPS, so a plan only ever shows amounts a person can measure:
  - count foods (roti, idli, egg, fruit): whole pieces            "2 pieces (86 g)"
  - cooked dishes measured in katori, bowl or cup (dal, rice, soup, couscous): halves    "1.5 katori (225 g)"
  - drinks measured in glasses: halves                             "1 glass (250 g)"
  - everything else: grams in 10 g steps (5 g for nuts)            "150 g"
Each food also has a minimum and a maximum number of steps (nobody eats 7 rotis or a thimble of rice), so the
solver cannot produce an absurd meal. This is separate from app/calc/portions.py, which turns a LOGGED portion
into grams and nutrition.
"""

import math
from dataclasses import dataclass

from app.calc.meal_pool import PoolFood

# Foods counted in pieces when they have a piece size, even if they also have a katori size.
PIECE_FIRST_CATEGORIES = frozenset({"dish_bread", "egg", "fruit", "dish_breakfast"})
PIECE_FIRST_KEYS = frozenset({"egg", "boiled_egg"})

MIN_PIECE_GRAMS = 15.0     # a smaller piece (an almond is 1.2 g) is not a meal unit: such foods are measured in grams
PIECE_BOUNDS = {"dish_bread": (1, 4), "egg": (1, 4), "dish_breakfast": (1, 5), "fruit": (1, 2)}   # (min, max) pieces
PIECE_BOUNDS_BY_KEY = {"egg": (1, 4), "boiled_egg": (1, 4),   # a food's own key wins over its category
                       "falafel": (2, 10),                          # 27 g each: a portion is about 5, never 1 to 3 (Step 7.10d)
                       "lamb_kofta": (2, 8), "stuffed_vine_leaves": (3, 10), "chicken_souvlaki": (1, 4),   # 45 g, 24 g and 80 g pieces
                       "paneer_tikka": (3, 10), "chicken_tikka": (2, 8)}                       # 32 g and 50 g pieces (Step 7.10d-3)
DEFAULT_PIECE_BOUNDS = (1, 3)
# Cooked dishes measured in a volume unit are counted in HALVES of it, whichever unit the food has (a katori of dal, a bowl of lentil
# soup, a cup of couscous), in this order of preference.
HALF_UNITS = ("katori", "bowl", "cup")
HALF_UNIT_BOUNDS = {                                # (min, max) half-unit steps: (1, 6) = 0.5 to 3 units
    "dish_rice": (1, 6), "dish_dal": (1, 4), "dish_sabzi": (1, 4), "dish_curry_meat": (1, 4),
    "dish_side": (1, 3), "dairy": (1, 4), "dish_breakfast": (1, 5),
    "dish_grain": (1, 6), "dish_legume": (1, 4), "dish_meat_fish": (1, 4), "dish_vegetable": (1, 4), "dish_dip": (1, 3), "dish_protein": (1, 4),
}
KATORI_BOUNDS = HALF_UNIT_BOUNDS                    # the old name
DEFAULT_KATORI_BOUNDS = (1, 4)
GLASS_BOUNDS = (1, 4)                               # half-glass steps: 0.5 to 2 glasses
GRAM_RULES = {                                      # category -> (step g, min g, max g)
    "nut_seed": (5, 10, 40), "fruit": (10, 80, 250), "dairy": (10, 50, 250), "dish_side": (10, 50, 200),
    "dish_dip": (10, 30, 120),                      # hummus and the like are eaten by the spoonful, not by the bowl
}
DEFAULT_GRAM_RULE = (10, 60, 300)


# A side dish, a breakfast extra or a snack must not grow into a second meal: cap its weight by ROLE.
ROLE_MAX_GRAMS = {"side": 260.0, "extra": 260.0, "snack": 300.0}
# On big days the main dishes may be bigger (a 3,000 kcal day needs it); side dishes, extras and snacks never grow.
SCALED_ROLES = frozenset({"staple", "protein", "vegetable", "main"})
MAX_PORTION_SCALE = 1.6


def portion_scale_for(kcal: float) -> float:
    """1.0 up to a 2,200 kcal day, then growing with the target, never above 1.6."""
    return round(min(MAX_PORTION_SCALE, max(1.0, kcal / 2200)), 2)


@dataclass(frozen=True)
class PortionSpec:
    step_g: float                  # grams in ONE step
    min_steps: int
    max_steps: int
    unit: str | None               # household unit shown to the user (a food_units unit), or None for grams
    unit_g: float | None           # grams in one whole unit (None for grams)
    steps_per_unit: float          # 1 for pieces, 2 for halves (so quantity = steps / steps_per_unit)


@dataclass(frozen=True)
class Portion:
    grams: float
    unit: str | None               # matches meal_plan_items.household_unit; None for plain grams
    quantity: float | None         # matches meal_plan_items.household_qty
    text: str                      # "1.5 katori (225 g)"


def portion_spec(food: PoolFood, role: str | None = None, scale: float = 1.0) -> PortionSpec:
    spec = _food_spec(food)
    if role in SCALED_ROLES and scale > 1.0:
        spec = PortionSpec(spec.step_g, spec.min_steps, math.ceil(spec.max_steps * scale), spec.unit, spec.unit_g,
                           spec.steps_per_unit)
    cap = ROLE_MAX_GRAMS.get(role or "")
    if cap is None:
        return spec
    max_steps = max(spec.min_steps, int(cap // spec.step_g))
    return PortionSpec(spec.step_g, spec.min_steps, min(spec.max_steps, max_steps), spec.unit, spec.unit_g, spec.steps_per_unit)


def _food_spec(food: PoolFood) -> PortionSpec:
    units = {u: g for u, g in food.units if u != "piece" or g >= MIN_PIECE_GRAMS}
    piece_first = food.category in PIECE_FIRST_CATEGORIES or food.key in PIECE_FIRST_KEYS
    half = next((u for u in HALF_UNITS if u in units), None)
    if "piece" in units and (piece_first or half is None):
        lo, hi = PIECE_BOUNDS_BY_KEY.get(food.key) or PIECE_BOUNDS.get(food.category, DEFAULT_PIECE_BOUNDS)
        return PortionSpec(units["piece"], lo, hi, "piece", units["piece"], 1)
    if half is not None:
        lo, hi = HALF_UNIT_BOUNDS.get(food.category, DEFAULT_KATORI_BOUNDS)
        return PortionSpec(units[half] / 2, lo, hi, half, units[half], 2)
    if "glass" in units:
        lo, hi = GLASS_BOUNDS
        return PortionSpec(units["glass"] / 2, lo, hi, "glass", units["glass"], 2)
    step, low_g, high_g = GRAM_RULES.get(food.category, DEFAULT_GRAM_RULE)
    return PortionSpec(float(step), -(-low_g // step), high_g // step, None, None, 1)


def describe(spec: PortionSpec, steps: int) -> Portion:
    """The amount for `steps` steps, as grams and as a household quantity."""
    if not spec.min_steps <= steps <= spec.max_steps:
        raise ValueError(f"{steps} steps is outside {spec.min_steps}-{spec.max_steps}")
    grams = round(steps * spec.step_g, 1)
    if spec.unit is None:
        return Portion(grams, None, None, f"{grams:g} g")
    qty = round(steps / spec.steps_per_unit, 2)
    name = spec.unit
    if name == "piece" and qty != 1:
        name = "pieces"
    return Portion(grams, spec.unit, qty, f"{qty:g} {name} ({grams:g} g)")
