"""Editing the profile after onboarding (Step 6.8, D-069). Plain code, no database, no LLM.

A change is a small dict like {"weight_kg": 74}. Each field belongs to one onboarding section (the same sections and the
same validation as the onboarding forms). This module knows which section a field is in and what a change makes stale:
the daily targets, the workout plan, the meal plan. It never edits a plan; it only says which ones no longer match.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

FIELDS: dict[str, tuple[str, ...]] = {
    "basics": ("display_name", "date_of_birth", "sex", "height_cm", "weight_kg", "activity_level"),
    "goal": ("goal_type", "target_weight_kg", "pace"),
    "preferences": ("diet_type", "cuisines", "disliked_foods"),
    "training": ("experience_level", "workout_location", "equipment", "days_per_week", "session_minutes"),
    "screening": ("pregnant_or_breastfeeding", "diabetes", "heart_or_bp", "kidney", "recent_surgery_or_injury",
                  "eating_disorder_history", "injury_areas"),
}
SECTION_OF: dict[str, str] = {field: section for section, fields in FIELDS.items() for field in fields}
ALL_FIELDS: tuple[str, ...] = tuple(f for fields in FIELDS.values() for f in fields)
SCREENING_FLAGS: tuple[str, ...] = FIELDS["screening"][:6]

# Fields that change the daily calorie and macro targets (the engine's inputs).
TARGET_FIELDS = frozenset({"date_of_birth", "sex", "height_cm", "weight_kg", "activity_level", "goal_type", "pace",
                           *SCREENING_FLAGS})
# Fields that make the active workout plan no longer match the person.
WORKOUT_FIELDS = frozenset({"experience_level", "workout_location", "equipment", "days_per_week", "session_minutes",
                            "injury_areas", "goal_type", "pace", *SCREENING_FLAGS})
# Fields that make the active meal plan no longer match the person (their targets or their diet).
MEAL_FIELDS = TARGET_FIELDS | {"diet_type", "disliked_foods", "cuisines"}


class UnknownFields(ValueError):
    """Fields that cannot be changed here (consent, ids, anything invented). Carries the names."""

    def __init__(self, fields: list[str]):
        super().__init__(f"fields that cannot be changed here: {fields}")
        self.fields = fields


def group_by_section(changes: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """{"weight_kg": 74, "diet_type": "vegan"} -> {"basics": {"weight_kg": 74}, "preferences": {"diet_type": "vegan"}}."""
    unknown = [field for field in changes if field not in SECTION_OF]
    if unknown:
        raise UnknownFields(unknown)
    grouped: dict[str, dict[str, Any]] = {}
    for field, value in changes.items():
        grouped.setdefault(SECTION_OF[field], {})[field] = value
    return grouped


@dataclass(frozen=True)
class Effects:
    targets_recalculated: bool
    workout_plan_stale: bool
    meal_plan_stale: bool

    def messages(self) -> list[str]:
        out = []
        if self.targets_recalculated:
            out.append("Your daily targets were updated to match your new details.")
        if self.workout_plan_stale:
            out.append("Your workout plan no longer matches your answers. Make a new one when you are ready.")
        if self.meal_plan_stale:
            out.append("Your meal plan no longer matches your answers. Make a new one when you are ready.")
        return out


def effects(changed: Collection[str]) -> Effects:
    """What a set of really-changed fields makes stale. Pure: it does not touch any plan."""
    changed = set(changed)
    return Effects(
        targets_recalculated=bool(changed & TARGET_FIELDS),
        workout_plan_stale=bool(changed & WORKOUT_FIELDS),
        meal_plan_stale=bool(changed & MEAL_FIELDS),
    )
