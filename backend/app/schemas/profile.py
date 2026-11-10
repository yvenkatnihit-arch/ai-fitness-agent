"""What the profile endpoints return."""

from datetime import date

from pydantic import BaseModel

from app.schemas.targets import TargetsOut, to_targets_out
from app.workflows.update_profile import ProfileUpdate


class ProfileOut(BaseModel):
    # basics
    display_name: str | None
    date_of_birth: date
    sex: str
    height_cm: float
    weight_kg: float             # the newest weigh-in
    activity_level: str
    # goal
    goal_type: str
    target_weight_kg: float | None
    pace: str
    # preferences
    diet_type: str
    cuisines: list[str]
    disliked_foods: list[str]
    # training
    experience_level: str
    workout_location: str
    equipment: list[str]
    days_per_week: int
    session_minutes: int | None  # None for accounts made before that question: plans assume 60
    # health screening
    pregnant_or_breastfeeding: bool
    diabetes: bool
    heart_or_bp: bool
    kidney: bool
    recent_surgery_or_injury: bool
    eating_disorder_history: bool
    injury_areas: list[str]


class ProfileUpdateOut(BaseModel):
    profile: ProfileOut
    changed: list[str]                  # the fields that really changed ([] when nothing did)
    targets_recalculated: bool
    targets: TargetsOut | None          # the new targets (numbers are None for users who must not see them)
    workout_plan_stale: bool            # the active plan no longer matches: make a new one (it still needs approval)
    meal_plan_stale: bool
    messages: list[str]                 # plain-English lines for the screen


def to_update_out(update: ProfileUpdate) -> ProfileUpdateOut:
    t = update.targets
    return ProfileUpdateOut(
        profile=ProfileOut(**update.profile),
        changed=list(update.changed),
        targets_recalculated=update.effects.targets_recalculated,
        targets=to_targets_out(t.calorie_target_kcal, t.protein_g, t.fat_g, t.carbs_g, list(t.reasons), t.doctor_note,
                               t.focus_on_habits) if t else None,
        workout_plan_stale=update.effects.workout_plan_stale,
        meal_plan_stale=update.effects.meal_plan_stale,
        messages=update.effects.messages(),
    )
