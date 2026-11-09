"""The workout edit request and response shapes."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.exercises import ExerciseOut
from app.schemas.plans import ActivePlanOut

ExerciseKey = Annotated[str, Field(pattern=r"^[a-z0-9_]{2,60}$")]
Day = Annotated[int, Field(ge=1, le=7, strict=True)]       # 1 = Monday
Position = Annotated[int, Field(ge=1, le=10, strict=True)]


class _Edit(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MoveDay(_Edit):
    op: Literal["move_day"]
    from_day: Day
    to_day: Day


class SwapExercise(_Edit):
    op: Literal["swap_exercise"]
    day: Day
    position: Position
    exercise_key: ExerciseKey


class RemoveExercise(_Edit):
    op: Literal["remove_exercise"]
    day: Day
    position: Position


class AddExercise(_Edit):
    op: Literal["add_exercise"]
    day: Day
    exercise_key: ExerciseKey


EditIn = Annotated[MoveDay | SwapExercise | RemoveExercise | AddExercise, Field(discriminator="op")]


class EditOut(BaseModel):
    message: str          # "Swapped Barbell Bench Press for Dumbbell Bench Press on Monday."
    plan: ActivePlanOut   # the plan as it is now


class OptionsOut(BaseModel):
    options: list[ExerciseOut]
