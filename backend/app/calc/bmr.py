"""Basal metabolic rate (BMR): calories burned per day at complete rest.

Mifflin-St Jeor equation:
    BMR = 10 * weight_kg + 6.25 * height_cm - 5 * age_years + s
where s = +5 (male), -161 (female), or -78 (other: the average of the two, D-009).
"""

from app.calc.validation import require_range
from app.safety import safety_config as cfg
from app.safety.safety_config import Sex

_SEX_CONSTANT: dict[Sex, float] = {
    "male": 5.0,
    "female": -161.0,
    "other": (5.0 + -161.0) / 2,  # -78.0
}


def bmr(weight_kg: float, height_cm: float, age_years: int, sex: Sex) -> float:
    """Return BMR in kcal/day. Raises ValueError for impossible or out-of-range inputs."""
    require_range("weight_kg", weight_kg, cfg.MIN_WEIGHT_KG, cfg.MAX_WEIGHT_KG)
    require_range("height_cm", height_cm, cfg.MIN_HEIGHT_CM, cfg.MAX_HEIGHT_CM)
    require_range("age_years", age_years, cfg.MIN_AGE_YEARS, cfg.MAX_AGE_YEARS)
    if sex not in _SEX_CONSTANT:
        raise ValueError(f"sex must be one of {sorted(_SEX_CONSTANT)}, got {sex!r}")

    return 10 * weight_kg + 6.25 * height_cm - 5 * age_years + _SEX_CONSTANT[sex]
