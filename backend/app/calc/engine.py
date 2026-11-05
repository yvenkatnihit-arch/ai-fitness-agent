"""The calculation engine in one call: profile in, daily targets out.

    BMR -> TDEE -> goal target -> safety clamps -> macros

Every number the app shows about targets comes from here, never from an LLM.
"""

from dataclasses import dataclass, field

from app.calc.bmr import bmr
from app.calc.clamps import apply_safety_clamps
from app.calc.macros import macros
from app.calc.targets import Goal, calorie_target
from app.calc.tdee import ActivityLevel, tdee
from app.safety.safety_config import Sex


@dataclass(frozen=True)
class BodyProfile:
    weight_kg: float
    height_cm: float
    age_years: int
    sex: Sex
    activity_level: ActivityLevel
    goal: Goal
    screening_flags: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Targets:
    bmr_kcal: float
    tdee_kcal: float
    goal_target_kcal: float   # what the goal asked for, before safety clamps
    calorie_target_kcal: float  # the safe target the plan uses
    protein_g: float
    fat_g: float
    carbs_g: float
    reasons: tuple[str, ...]  # every limit that changed something, in order
    doctor_note: bool
    focus_on_habits: bool


def calculate_targets(profile: BodyProfile) -> Targets:
    """Run the full chain. Raises ValueError for any invalid input."""
    flags = set(profile.screening_flags)

    bmr_kcal = bmr(profile.weight_kg, profile.height_cm, profile.age_years, profile.sex)
    tdee_kcal = tdee(bmr_kcal, profile.activity_level)
    goal_kcal = calorie_target(tdee_kcal, profile.goal)
    safe = apply_safety_clamps(goal_kcal, tdee_kcal, profile.weight_kg, profile.sex, flags)
    split = macros(safe.kcal, profile.weight_kg, profile.goal, flags)

    return Targets(
        bmr_kcal=bmr_kcal,
        tdee_kcal=tdee_kcal,
        goal_target_kcal=goal_kcal,
        calorie_target_kcal=safe.kcal,
        protein_g=split.protein_g,
        fat_g=split.fat_g,
        carbs_g=split.carbs_g,
        reasons=safe.reasons + split.reasons,
        doctor_note=safe.doctor_note,
        focus_on_habits=safe.focus_on_habits,
    )
