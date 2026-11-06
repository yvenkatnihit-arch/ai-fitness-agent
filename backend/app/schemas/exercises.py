"""What the exercise endpoint returns."""

from pydantic import BaseModel

from app.calc.exercise_filter import ExerciseOption


class ExerciseOut(BaseModel):
    id: int
    key: str
    name: str
    muscle_groups: list[str]   # the first one is the main muscle
    equipment: list[str]       # empty = bodyweight only
    location: str
    difficulty: str
    movement_pattern: str
    form_cues: list[str]       # 2-4 short lines
    verified: bool             # False = injury tags not signed off yet (data/reports/exercises_review.md)


class ExerciseListOut(BaseModel):
    setting: str               # 'gym' or 'home': which place this list is for
    level: str
    injuries: list[str]
    total_in_library: int
    shown: int
    exercises: list[ExerciseOut]


def to_exercise_out(option: ExerciseOption) -> ExerciseOut:
    return ExerciseOut(
        id=option.id, key=option.key, name=option.name, muscle_groups=list(option.muscle_groups),
        equipment=list(option.equipment), location=option.location, difficulty=option.difficulty,
        movement_pattern=option.movement_pattern, form_cues=list(option.form_cues),
        verified=option.review_status == "ready",
    )
