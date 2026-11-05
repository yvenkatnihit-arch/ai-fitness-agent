"""Daily macros: protein, fat and carbs in grams, from the safe calorie target.

  1. Protein = body weight * g/kg for the goal
       capped at 0.8 g/kg with the kidney flag, and at 35% of calories
  2. Fat     = 25% of calories (the minimum, D-023)
  3. Carbs   = whatever calories are left
Protein and carbs have 4 kcal/g, fat has 9 kcal/g, so the three always add up to the target.
"""

from dataclasses import dataclass

from app.calc.targets import Goal
from app.calc.validation import require_positive, require_range
from app.safety import safety_config as cfg

KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARBS = 4
KCAL_PER_G_FAT = 9

# Protein in grams per kg of body weight, by goal (D-023).
PROTEIN_G_PER_KG: dict[Goal, float] = {
    "fat_loss": 2.0,         # keep muscle in a deficit
    "recomp": 2.0,
    "muscle_gain": 1.8,
    "weight_gain": 1.6,
    "general_fitness": 1.6,
}

# Reason codes, like the ones in clamps.py.
KIDNEY_PROTEIN_CAP = "kidney_protein_cap"
PROTEIN_CALORIE_CAP = "protein_calorie_cap"


@dataclass(frozen=True)
class Macros:
    protein_g: float
    fat_g: float
    carbs_g: float
    reasons: tuple[str, ...]


def macros(target_kcal: float, weight_kg: float, goal: Goal, screening_flags: set[str]) -> Macros:
    """Split the daily calorie target into protein, fat and carbs (grams)."""
    require_positive("target_kcal", target_kcal)
    require_range("weight_kg", weight_kg, cfg.MIN_WEIGHT_KG, cfg.MAX_WEIGHT_KG)
    if goal not in PROTEIN_G_PER_KG:
        raise ValueError(f"goal must be one of {list(PROTEIN_G_PER_KG)}, got {goal!r}")
    cfg.check_screening_flags(screening_flags)

    reasons: list[str] = []

    # 1. Protein
    protein_g = weight_kg * PROTEIN_G_PER_KG[goal]
    if "kidney" in screening_flags:
        kidney_max = weight_kg * cfg.KIDNEY_MAX_PROTEIN_G_PER_KG
        if protein_g > kidney_max:
            protein_g = kidney_max
            reasons.append(KIDNEY_PROTEIN_CAP)
    calorie_max = target_kcal * cfg.MAX_PROTEIN_KCAL_FRACTION / KCAL_PER_G_PROTEIN
    if protein_g > calorie_max:
        protein_g = calorie_max
        reasons.append(PROTEIN_CALORIE_CAP)

    # 2. Fat
    fat_g = target_kcal * cfg.MIN_FAT_KCAL_FRACTION / KCAL_PER_G_FAT

    # 3. Carbs fill the rest. Protein <= 35% and fat = 25%, so carbs are always >= 40%.
    carbs_kcal = target_kcal - protein_g * KCAL_PER_G_PROTEIN - fat_g * KCAL_PER_G_FAT
    carbs_g = carbs_kcal / KCAL_PER_G_CARBS

    return Macros(protein_g=protein_g, fat_g=fat_g, carbs_g=carbs_g, reasons=tuple(reasons))
