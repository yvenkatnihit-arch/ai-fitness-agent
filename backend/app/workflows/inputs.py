"""Turn the saved onboarding answers into the calculation engine's input (shared by targets and forecasts)."""

from datetime import date

from app.calc.age import age_on
from app.calc.engine import BodyProfile
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
