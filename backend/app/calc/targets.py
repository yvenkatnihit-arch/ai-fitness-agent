"""Calorie target by goal and pace: TDEE adjusted up (surplus) or down (deficit).

    target = TDEE * (1 + adjustment[goal][pace])

This is the *ideal* target for the goal and pace (D-021, D-042). Safety clamps (calorie floor,
screening flags, weight-loss rate) are applied afterwards and can only make the target more
conservative, so no pace can go past a limit in safety_config.py.
"""

from typing import Literal

from app.calc.validation import require_positive
from app.core.vocabulary import PACES, Pace

Goal = Literal["fat_loss", "muscle_gain", "weight_gain", "recomp", "general_fitness"]

# Fraction of TDEE: negative = deficit, positive = surplus. "normal" is the original D-021 value.
# "fast" is the largest change the safety limits allow (25% deficit, 10% surplus); "slow" is about half of normal.
# Recomposition stays gentle on purpose: it is a slow, steady goal, so "fast" only means a slightly bigger deficit.
GOAL_ADJUSTMENT: dict[Goal, dict[Pace, float]] = {
    "fat_loss":        {"slow": -0.10, "normal": -0.20, "fast": -0.25},
    "muscle_gain":     {"slow": 0.04, "normal": 0.08, "fast": 0.10},
    "weight_gain":     {"slow": 0.05, "normal": 0.10, "fast": 0.10},
    "recomp":          {"slow": -0.05, "normal": -0.10, "fast": -0.15},
    "general_fitness": {"slow": 0.0, "normal": 0.0, "fast": 0.0},
}

# Reason code shown when we hold a "fast" request back because of the user's health answers.
PACE_LIMITED_BY_SCREENING = "pace_limited_by_screening"


def effective_pace(pace: Pace, goal: Goal, screening_flags: frozenset[str] | set[str]) -> tuple[Pace, bool]:
    """The pace we actually use, and whether we held the user's choice back.

    Anyone with a health flag (diabetes, pregnancy, eating-disorder history...) gets at most "normal":
    the clamps already soften their deficit, but we don't aim them at the intense end either.
    Goals that don't change weight (general fitness) have nothing to hold back.
    """
    if pace == "fast" and screening_flags:
        return "normal", goal != "general_fitness"
    return pace, False


def calorie_target(tdee_kcal: float, goal: Goal, pace: Pace = "normal") -> float:
    """Return the ideal daily calorie target in kcal for this goal and pace (before safety clamps)."""
    require_positive("tdee_kcal", tdee_kcal)
    if goal not in GOAL_ADJUSTMENT:
        raise ValueError(f"goal must be one of {list(GOAL_ADJUSTMENT)}, got {goal!r}")
    if pace not in PACES:
        raise ValueError(f"pace must be one of {list(PACES)}, got {pace!r}")

    return tdee_kcal * (1 + GOAL_ADJUSTMENT[goal][pace])
