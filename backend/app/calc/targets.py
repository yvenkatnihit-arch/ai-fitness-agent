"""Calorie target by goal: TDEE adjusted up (surplus) or down (deficit).

    target = TDEE * (1 + adjustment)

This is the *ideal* target for the goal (D-021). Safety clamps (calorie floor,
screening flags, weight-loss rate) are applied afterwards in Step 1.5 and can only
make the target more conservative.
"""

from typing import Literal

from app.calc.validation import require_positive

Goal = Literal["fat_loss", "muscle_gain", "weight_gain", "recomp", "general_fitness"]

# Fraction of TDEE: negative = deficit, positive = surplus.
GOAL_ADJUSTMENT: dict[Goal, float] = {
    "fat_loss": -0.20,        # sustainable deficit, ~0.5 kg/week for most people
    "muscle_gain": 0.08,      # lean bulk
    "weight_gain": 0.10,      # at the surplus cap (D-010)
    "recomp": -0.10,          # small deficit + high protein
    "general_fitness": 0.0,   # maintenance
}


def calorie_target(tdee_kcal: float, goal: Goal) -> float:
    """Return the goal's ideal daily calorie target in kcal (before safety clamps)."""
    require_positive("tdee_kcal", tdee_kcal)
    if goal not in GOAL_ADJUSTMENT:
        raise ValueError(f"goal must be one of {list(GOAL_ADJUSTMENT)}, got {goal!r}")

    return tdee_kcal * (1 + GOAL_ADJUSTMENT[goal])
