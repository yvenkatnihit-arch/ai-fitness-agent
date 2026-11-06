"""Which exercises can this user do? Pure Python, no database, no LLM (Step 5.4).

Plans may only use exercises that pass this filter, so every rule errs on the side of hiding an exercise:
  1. Injuries: an exercise tagged with any body area the user reported is hidden.
  2. Experience: an exercise harder than the user's level is hidden.
  3. Place: the exercise must suit where they train (gym, or home).
  4. Equipment: at home, only equipment they own. A gym is assumed to have all of it.

A user who trains in "both" places is filtered once per place (a plan day is either a gym day or a home day).
"""

from dataclasses import dataclass
from typing import Literal

Setting = Literal["gym", "home"]
LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


@dataclass(frozen=True)
class ExerciseOption:
    id: int
    key: str
    name: str
    muscle_groups: tuple[str, ...]
    equipment: tuple[str, ...]
    location: str
    difficulty: str
    movement_pattern: str
    form_cues: tuple[str, ...]
    contraindications: tuple[str, ...]
    review_status: str


@dataclass(frozen=True)
class ExerciseNeeds:
    setting: Setting
    level: str
    injuries: frozenset[str]
    owned_equipment: frozenset[str]


def setting_for(workout_location: str, requested: Setting | None = None) -> Setting:
    """The place to filter for. Someone who trains in 'both' places gets the gym unless they ask for home."""
    if requested is not None:
        return requested
    return "home" if workout_location == "home" else "gym"


def why_hidden(option: ExerciseOption, needs: ExerciseNeeds) -> str | None:
    """The first reason this exercise is not for this user, or None when it is fine."""
    hurt = [area for area in option.contraindications if area in needs.injuries]
    if hurt:
        return f"injury: {', '.join(hurt)}"
    if LEVEL_ORDER[option.difficulty] > LEVEL_ORDER[needs.level]:
        return f"too hard: {option.difficulty}"
    if option.location not in (needs.setting, "both"):
        return f"not a {needs.setting} exercise"
    if needs.setting == "home":
        missing = [item for item in option.equipment if item not in needs.owned_equipment]
        if missing:
            return f"needs equipment: {', '.join(missing)}"
    return None


def filter_exercises(options: list[ExerciseOption], needs: ExerciseNeeds) -> list[ExerciseOption]:
    return [option for option in options if why_hidden(option, needs) is None]
