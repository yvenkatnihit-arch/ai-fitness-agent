"""What each onboarding form may send. FastAPI rejects anything else with a 422 before our code runs.

Rules for every model:
- extra="forbid": unknown fields are refused (nobody can slip in user_id or onboarded_at).
- Strings are trimmed; numbers are range-checked with the same limits as the database (D-019).
- Health answers are strict booleans: "yes" or 1 is refused, only true/false.
"""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.calc.age import age_on
from app.calc.targets import Goal
from app.calc.tdee import ActivityLevel
from app.core.time import india_today
from app.core.vocabulary import (
    EQUIPMENT, MAX_CUISINES, Cuisine, DietType, Equipment, ExperienceLevel, InjuryArea, Pace, SessionMinutes, WorkoutLocation,
)
from app.safety import safety_config as cfg
from app.safety.safety_config import Sex

StrictBool = Annotated[bool, Field(strict=True)]
WeightKg = Annotated[float, Field(ge=cfg.MIN_WEIGHT_KG, le=cfg.MAX_WEIGHT_KG, strict=True)]
FoodName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class _Form(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _unique(items: list) -> list:
    """Drop repeats, keep the user's order."""
    return list(dict.fromkeys(items))


class ConsentIn(_Form):
    """Step 1: agree to health-data processing before anything else is stored (DPDP)."""

    # Strict bool: only JSON true/false (Python treats 1 == True, so 1 must not count as consent).
    health_data_consent: StrictBool
    privacy_notice_version: str = Field(min_length=1, max_length=20)

    @field_validator("health_data_consent")
    @classmethod
    def must_agree(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("consent to process health data is required to continue")
        return value


class BasicsIn(_Form):
    """Step 1: body basics. weight_kg becomes the first body_weight_entries row."""

    display_name: str | None = Field(default=None, max_length=80)
    date_of_birth: date
    sex: Sex
    height_cm: float = Field(ge=cfg.MIN_HEIGHT_CM, le=cfg.MAX_HEIGHT_CM, strict=True)
    weight_kg: WeightKg
    activity_level: ActivityLevel

    @field_validator("date_of_birth")
    @classmethod
    def adult_and_plausible(cls, value: date) -> date:
        today = india_today()
        if value > today:
            raise ValueError("date of birth can't be in the future")
        age = age_on(value, today)
        if age < cfg.MIN_AGE_YEARS:
            raise ValueError(f"you must be at least {cfg.MIN_AGE_YEARS} to use this app")
        if age > cfg.MAX_AGE_YEARS:
            raise ValueError(f"please check the date of birth (age over {cfg.MAX_AGE_YEARS})")
        return value


class GoalIn(_Form):
    """Step 2: what the user wants."""

    goal_type: Goal
    target_weight_kg: WeightKg | None = None
    pace: Pace = "normal"  # D-042: slow / normal / fast, always inside the safety limits


class PreferencesIn(_Form):
    """Step 3: diet and foods to avoid."""

    diet_type: DietType
    cuisines: list[Cuisine] = Field(default_factory=lambda: ["indian"], min_length=1, max_length=MAX_CUISINES)   # D-088: one or more
    disliked_foods: list[FoodName] = Field(default_factory=list, max_length=30)

    @field_validator("cuisines")
    @classmethod
    def no_repeated_cuisines(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("pick each cuisine once")
        return value

    @field_validator("disliked_foods")
    @classmethod
    def no_repeats(cls, value: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for item in value:
            seen.setdefault(item.casefold(), item)  # "Brinjal" and "brinjal" count once
        return list(seen.values())


class TrainingIn(_Form):
    """Step 4: where and how the user trains."""

    experience_level: ExperienceLevel
    workout_location: WorkoutLocation
    equipment: list[Equipment] = Field(default_factory=list, max_length=len(EQUIPMENT))
    days_per_week: int = Field(ge=1, le=7, strict=True)
    session_minutes: SessionMinutes   # how long one session can last: 30, 45, 60 or 90

    @field_validator("equipment")
    @classmethod
    def no_repeated_equipment(cls, value: list[str]) -> list[str]:
        return _unique(value)


class ScreeningIn(_Form):
    """Step 5: health screening. Every question must be answered (no defaults)."""

    pregnant_or_breastfeeding: StrictBool
    diabetes: StrictBool
    heart_or_bp: StrictBool
    kidney: StrictBool
    recent_surgery_or_injury: StrictBool
    eating_disorder_history: StrictBool
    injury_areas: list[InjuryArea] = Field(default_factory=list)

    @field_validator("injury_areas")
    @classmethod
    def no_repeated_injuries(cls, value: list[str]) -> list[str]:
        return _unique(value)

    def flags(self) -> set[str]:
        """The flags that are true, in safety_config.SCREENING_FLAGS terms."""
        return {name for name in cfg.SCREENING_FLAGS if getattr(self, name)}
