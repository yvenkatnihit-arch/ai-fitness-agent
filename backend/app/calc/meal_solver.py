"""The portion solver: given the dishes chosen for a day, work out how much of each (Step 6.7b, D-065).

"The LLM selects, a solver computes": the model only names dishes; THIS code does all the arithmetic, with a
mixed-integer linear program (scipy / HiGHS). The unknowns are whole numbers of household steps (see
meal_portions.py), so every amount is something a person can measure and there is no rounding afterwards.

Hard limits (the plan can never break them):
  - calories inside a band around the target, built with the engine's own safety clamps (floor, deficit and
    surplus caps, weekly-loss cap, health-flag caps), so safety_config.py stays the single source of truth;
  - protein never above its cap (the kidney flag caps it at the target itself);
  - every portion between its minimum and maximum step count.
Soft goals (minimised): distance of protein, carbs, fat and calories from target, each meal's distance from its
share of the day, and distance from a comfortable portion.

The answer is honest: it reports what was achieved and a list of `issues` in plain words, which the dish picker
(Step 6.7c) uses to ask the model for different dishes. If the dishes cannot fit at all it says "infeasible".
"""

import dataclasses
import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from app.calc.clamps import apply_safety_clamps
from app.calc.engine import Targets
from app.calc.meal_pool import SLOT_CALORIE_SHARE, PoolFood
from app.calc.meal_portions import Portion, describe, portion_spec
from app.calc.portions import Nutrition, Per100g, nutrition_for
from app.safety import safety_config as cfg

logger = logging.getLogger(__name__)

KCAL_BAND = 0.04            # calories may sit within 4% of the target (still inside the safety clamps)
PROTEIN_HEADROOM = 1.15     # protein may go up to 15% over target (never over the cap below)
KCAL_MARGIN = 1.0           # keep this far inside the hard band so per-item rounding to 0.1 can never leave it
PROTEIN_MARGIN_G = 0.5
VERIFY_TOLERANCE_KCAL = 1.5
TIME_LIMIT_S = 10.0
# Weights of the soft goals (relative importance; each deviation is first divided by its target).
W_KCAL, W_PROTEIN, W_FAT, W_CARBS, W_SLOT, W_COMFORT = 4.0, 4.0, 1.5, 1.0, 1.0, 0.05
# Quality thresholds that produce `issues` (the plan is still returned; the picker may ask for better dishes).
MIN_PROTEIN_FRACTION = 0.90
FAT_RANGE = (0.70, 1.25)
CARB_RANGE = (0.70, 1.30)
SLOT_TOLERANCE = 0.35       # a meal may be this far (as a fraction) from its share of the day's calories


@dataclass(frozen=True)
class DayTargets:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    kcal_min: float             # hard band
    kcal_max: float
    protein_max_g: float        # hard cap


def day_targets(t: Targets, *, weight_kg: float, sex: cfg.Sex, flags: Collection[str]) -> DayTargets:
    """Turn the engine's daily targets into the solver's targets plus its hard limits."""
    flags = set(flags)
    target = t.calorie_target_kcal
    low = apply_safety_clamps(target * (1 - KCAL_BAND), t.tdee_kcal, weight_kg, sex, flags).kcal
    high = apply_safety_clamps(target * (1 + KCAL_BAND), t.tdee_kcal, weight_kg, sex, flags).kcal
    low, high = min(low, target), max(high, target)   # the target itself is always inside its own band
    if "kidney" in flags:
        protein_max = t.protein_g    # the target already IS the kidney cap (D-023): never above it
    else:
        protein_max = min(t.protein_g * PROTEIN_HEADROOM, cfg.MAX_PROTEIN_KCAL_FRACTION * high / 4)
    return DayTargets(target, t.protein_g, t.carbs_g, t.fat_g, low, high, protein_max)


@dataclass(frozen=True)
class MealItem:
    slot: str
    role: str
    food: PoolFood


@dataclass(frozen=True)
class SolvedItem:
    slot: str
    role: str
    food_key: str
    food_name: str
    steps: int
    portion: Portion
    nutrition: Nutrition


@dataclass(frozen=True)
class DaySolution:
    status: str                              # "ok" | "issues" | "infeasible"
    items: tuple[SolvedItem, ...]
    totals: Nutrition
    percent_of_target: Mapping[str, float]   # kcal / protein / carbs / fat as % of the day's target
    slot_kcal: Mapping[str, float]
    issues: tuple[str, ...]                  # plain words, for the picker's repair step and for us


_EMPTY = Nutrition(0.0, 0.0, 0.0, 0.0)
NO_COMBINATION = "no combination of these dishes"


def _infeasible(issues: list[str]) -> DaySolution:
    return DaySolution("infeasible", (), _EMPTY, {}, {}, tuple(issues))


def solve_day(items: Sequence[MealItem], targets: DayTargets, shares: Mapping[str, float] = SLOT_CALORIE_SHARE,
              portion_scale: float = 1.0) -> DaySolution:
    """Portions for the chosen dishes, or an honest explanation of why they cannot work."""
    result = _solve(items, targets, shares, portion_scale)
    if result.status == "infeasible" and result.issues and result.issues[0].startswith(NO_COMBINATION):
        # Is the PROTEIN CAP the reason? Solve again without it: if that works, say how much protein these dishes need.
        relaxed = _solve(items, dataclasses.replace(targets, protein_max_g=1e9), shares, portion_scale)
        if relaxed.status != "infeasible":
            return _infeasible([f"these dishes need about {relaxed.totals.protein_g:.0f} g of protein to reach the "
                                f"calorie minimum, above the {targets.protein_max_g:.0f} g protein cap: choose lower-protein dishes"])
    return result


def _solve(items: Sequence[MealItem], targets: DayTargets, shares: Mapping[str, float],
           portion_scale: float) -> DaySolution:
    if not items:
        raise ValueError("a day needs at least one item")
    n = len(items)
    specs = [portion_spec(i.food, i.role, portion_scale) for i in items]
    foods = [Per100g(i.food.kcal, i.food.protein_g, i.food.carbs_g, i.food.fat_g) for i in items]
    # Nutrition in ONE step of each item.
    a_k = np.array([f.kcal * s.step_g / 100 for f, s in zip(foods, specs)])
    a_p = np.array([f.protein_g * s.step_g / 100 for f, s in zip(foods, specs)])
    a_c = np.array([f.carbs_g * s.step_g / 100 for f, s in zip(foods, specs)])
    a_f = np.array([f.fat_g * s.step_g / 100 for f, s in zip(foods, specs)])
    lo = np.array([s.min_steps for s in specs], dtype=float)
    hi = np.array([s.max_steps for s in specs], dtype=float)

    # Quick, explainable infeasibility: even the smallest or the largest portions cannot reach the band.
    smallest, largest = float(a_k @ lo), float(a_k @ hi)
    if smallest > targets.kcal_max:
        return _infeasible([f"even the smallest portions of these dishes give {smallest:.0f} kcal, above the "
                            f"{targets.kcal_max:.0f} kcal limit: choose lighter dishes"])
    if largest < targets.kcal_min:
        return _infeasible([f"even the largest portions of these dishes give only {largest:.0f} kcal, below the "
                            f"{targets.kcal_min:.0f} kcal minimum: choose more filling dishes"])

    slots = list(dict.fromkeys(i.slot for i in items))
    share_total = sum(shares[s] for s in slots)
    slot_target = {s: shares[s] / share_total * targets.kcal for s in slots}
    comfort = np.rint((lo + hi) / 2)

    # Variable layout: n steps | dK+ dK- dP+ dP- dC+ dC- dF+ dF- | slot+/- per slot | comfort+/- per item
    base = n
    dev = {name: base + 2 * k for k, name in enumerate(["kcal", "protein", "carbs", "fat"])}
    slot_at = {s: base + 8 + 2 * k for k, s in enumerate(slots)}
    comfort_at = base + 8 + 2 * len(slots)
    nv = comfort_at + 2 * n

    cost = np.zeros(nv)
    for name, weight, target in (("kcal", W_KCAL, targets.kcal), ("protein", W_PROTEIN, targets.protein_g),
                                 ("carbs", W_CARBS, targets.carbs_g), ("fat", W_FAT, targets.fat_g)):
        cost[dev[name]] = cost[dev[name] + 1] = weight / max(target, 1.0)
    for s in slots:
        cost[slot_at[s]] = cost[slot_at[s] + 1] = W_SLOT / max(targets.kcal, 1.0)
    for i in range(n):
        cost[comfort_at + 2 * i] = cost[comfort_at + 2 * i + 1] = W_COMFORT / (hi[i] - lo[i] + 1)

    rows: list[np.ndarray] = []
    row_lo: list[float] = []
    row_hi: list[float] = []

    def add(row: np.ndarray, low: float, high: float) -> None:
        rows.append(row)
        row_lo.append(low)
        row_hi.append(high)

    def line(coeff: np.ndarray) -> np.ndarray:
        r = np.zeros(nv)
        r[:n] = coeff
        return r

    band_low, band_high = targets.kcal_min, targets.kcal_max
    if band_high - band_low > 10:                       # keep a small margin inside the hard band
        band_low, band_high = band_low + KCAL_MARGIN, band_high - KCAL_MARGIN
    add(line(a_k), band_low, band_high)                                       # calories in the safe band
    add(line(a_p), -np.inf, targets.protein_max_g - PROTEIN_MARGIN_G)         # protein under its cap
    for name, coeff, target in (("kcal", a_k, targets.kcal), ("protein", a_p, targets.protein_g),
                                ("carbs", a_c, targets.carbs_g), ("fat", a_f, targets.fat_g)):
        r = line(coeff)
        r[dev[name]], r[dev[name] + 1] = -1.0, 1.0                            # total - d+ + d- = target
        add(r, target, target)
    for s in slots:
        r = np.zeros(nv)
        for i, item in enumerate(items):
            if item.slot == s:
                r[i] = a_k[i]
        r[slot_at[s]], r[slot_at[s] + 1] = -1.0, 1.0
        add(r, slot_target[s], slot_target[s])
    for i in range(n):
        r = np.zeros(nv)
        r[i], r[comfort_at + 2 * i], r[comfort_at + 2 * i + 1] = 1.0, -1.0, 1.0
        add(r, comfort[i], comfort[i])

    lower = np.zeros(nv)
    upper = np.full(nv, np.inf)
    lower[:n], upper[:n] = lo, hi
    integrality = np.zeros(nv)
    integrality[:n] = 1
    result = milp(cost, constraints=LinearConstraint(np.array(rows), np.array(row_lo), np.array(row_hi)),
                  integrality=integrality, bounds=Bounds(lower, upper), options={"time_limit": TIME_LIMIT_S})
    if result.x is None:
        return _infeasible([f"{NO_COMBINATION} fits the calorie limits: choose different dishes"])

    steps = np.clip(np.rint(result.x[:n]).astype(int), lo.astype(int), hi.astype(int))
    solved = []
    for item, spec, per, count in zip(items, specs, foods, steps):
        portion = describe(spec, int(count))
        solved.append(SolvedItem(item.slot, item.role, item.food.key, item.food.name, int(count), portion,
                                 nutrition_for(portion.grams, per)))
    totals = Nutrition(*(round(sum(getattr(s.nutrition, k) for s in solved), 1)
                         for k in ("kcal", "protein_g", "carbs_g", "fat_g")))

    # Verify the hard limits on the numbers the user will actually see (never trust the solver blindly).
    if not (targets.kcal_min - VERIFY_TOLERANCE_KCAL <= totals.kcal <= targets.kcal_max + VERIFY_TOLERANCE_KCAL
            and totals.protein_g <= targets.protein_max_g + VERIFY_TOLERANCE_KCAL):
        logger.error("meal solver result broke a hard limit: %s vs %s", totals, targets)
        return _infeasible(["the solver's answer failed the safety check: choose different dishes"])

    percent = {"kcal": 100 * totals.kcal / targets.kcal, "protein": 100 * totals.protein_g / targets.protein_g,
               "carbs": 100 * totals.carbs_g / targets.carbs_g, "fat": 100 * totals.fat_g / targets.fat_g}
    slot_kcal = {s: round(sum(x.nutrition.kcal for x in solved if x.slot == s), 1) for s in slots}
    issues: list[str] = []
    if percent["protein"] < MIN_PROTEIN_FRACTION * 100:
        issues.append(f"protein is only {percent['protein']:.0f}% of the target: use a more protein-rich dish")
    for name, (low, high) in (("fat", FAT_RANGE), ("carbs", CARB_RANGE)):
        if percent[name] < low * 100:
            issues.append(f"{name} is only {percent[name]:.0f}% of the target: the dishes are too low in {name}")
        elif percent[name] > high * 100:
            issues.append(f"{name} is {percent[name]:.0f}% of the target: the dishes are too high in {name}")
    for s in slots:
        want = slot_target[s]
        if abs(slot_kcal[s] - want) > SLOT_TOLERANCE * want:
            issues.append(f"{s} has {slot_kcal[s]:.0f} kcal but should have about {want:.0f}")
    return DaySolution("issues" if issues else "ok", tuple(solved), totals, percent, slot_kcal, tuple(issues))
