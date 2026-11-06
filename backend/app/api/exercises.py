from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.calc.exercise_filter import ExerciseNeeds, Setting, filter_exercises, setting_for
from app.core.auth import CurrentUser, get_current_user
from app.db import exercises as repo
from app.db import user_transaction
from app.schemas.exercises import ExerciseListOut, to_exercise_out

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("/for-me", response_model=ExerciseListOut)
def for_me(
    setting: Annotated[Setting | None, Query(description="gym or home; defaults from your onboarding answer")] = None,
    user: CurrentUser = Depends(get_current_user),
) -> ExerciseListOut:
    """The exercises this user can do: their level, their place and equipment, minus anything
    that could aggravate a reported injury (no LLM: a database read plus plain rules)."""
    with user_transaction(user.id) as conn:
        context = repo.read_training_context(conn)
        library = repo.list_exercises(conn) if context else []
    if context is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Please finish the training and health steps of onboarding first.")
    needs = ExerciseNeeds(setting_for(context.workout_location, setting), context.level, context.injuries, context.equipment)
    shown = filter_exercises(library, needs)
    return ExerciseListOut(
        setting=needs.setting, level=needs.level, injuries=sorted(needs.injuries),
        total_in_library=len(library), shown=len(shown), exercises=[to_exercise_out(e) for e in shown],
    )
