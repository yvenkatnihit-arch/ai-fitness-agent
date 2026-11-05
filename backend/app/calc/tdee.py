"""Total daily energy expenditure (TDEE): calories burned per day including activity.

    TDEE = BMR * activity multiplier

Standard multipliers (D-020). The descriptions are what onboarding shows the user.
"""

from typing import Literal

from app.calc.validation import require_positive

ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]

ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    "sedentary": 1.2,     # desk job, little or no exercise
    "light": 1.375,       # exercise 1-3 days a week
    "moderate": 1.55,     # exercise 3-5 days a week
    "active": 1.725,      # exercise 6-7 days a week
    "very_active": 1.9,   # hard daily training or a physical job
}


def tdee(bmr_kcal: float, activity_level: ActivityLevel) -> float:
    """Return TDEE in kcal/day. Raises ValueError for a bad BMR or unknown activity level."""
    require_positive("bmr_kcal", bmr_kcal)
    if activity_level not in ACTIVITY_MULTIPLIERS:
        raise ValueError(
            f"activity_level must be one of {list(ACTIVITY_MULTIPLIERS)}, got {activity_level!r}"
        )

    return bmr_kcal * ACTIVITY_MULTIPLIERS[activity_level]
