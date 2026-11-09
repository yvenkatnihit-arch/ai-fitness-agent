"""Turn the saved onboarding answers into the calculation engine's input (shared by targets and forecasts)."""

from dataclasses import dataclass
from datetime import date

from app.calc.age import age_on
from app.calc.engine import BodyProfile, Targets, calculate_targets
from app.calc.meal_solver import DayTargets, day_targets
from app.calc.meal_week import emphasis_for
from app.db.targets import SavedInputs


def body_profile(saved: SavedInputs, today: date) -> BodyProfile:
    return BodyProfile(
        weight_kg=saved.weight_kg,
        height_cm=saved.height_cm,
        age_years=age_on(saved.date_of_birth, today),
        sex=saved.sex,
        activity_level=saved.activity_level,
        goal=saved.goal_type,
        screening_flags=saved.flags,
        pace=saved.pace,
    )


@dataclass(frozen=True)
class MealTargets:
    engine: Targets
    day: DayTargets
    emphasis: str | None
    numbers_hidden: bool     # eating-disorder history: balanced meals, no calorie or macro numbers (brief section 7)


def meal_targets(saved: SavedInputs, today: date) -> MealTargets:
    """The engine's targets for this user plus the meal solver's hard limits, recomputed from what is saved today."""
    engine = calculate_targets(body_profile(saved, today))
    day = day_targets(engine, weight_kg=saved.weight_kg, sex=saved.sex, flags=saved.flags)
    return MealTargets(engine, day, emphasis_for(engine.protein_g, engine.calorie_target_kcal, saved.flags),
                       engine.focus_on_habits)
