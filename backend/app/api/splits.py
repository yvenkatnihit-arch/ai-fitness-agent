from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.calc.splits import fits_days, recommend_splits, split_by_key
from app.core.auth import CurrentUser, get_current_user
from app.db import splits as repo
from app.db import user_transaction
from app.schemas.splits import SplitChoiceIn, SplitChoiceOut, SplitRecommendationsOut, to_recommendation_out

router = APIRouter(prefix="/splits", tags=["splits"])

NOT_READY = "Please finish the goal and training steps of onboarding first."


@router.get("/recommend", response_model=SplitRecommendationsOut)
def recommend(
    days: Annotated[int | None, Query(ge=1, le=7, description="Try a different number of days a week")] = None,
    user: CurrentUser = Depends(get_current_user),
) -> SplitRecommendationsOut:
    """Workout splits that fit this user's days, level and goal, best first (no LLM: plain rules)."""
    with user_transaction(user.id) as conn:
        inputs = repo.read_split_inputs(conn)
    if inputs is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NOT_READY)
    chosen_days = days or inputs.days_per_week
    recommendations = recommend_splits(chosen_days, inputs.level, inputs.goal)
    # A choice only counts while it still fits (the user may have changed their training days since).
    chosen = inputs.chosen_key if inputs.chosen_key and fits_days(inputs.chosen_key, chosen_days) else None
    return SplitRecommendationsOut(
        days_per_week=chosen_days, level=inputs.level, goal=inputs.goal, chosen_key=chosen,
        recommendations=[to_recommendation_out(r) for r in recommendations],
    )


@router.put("/choice", response_model=SplitChoiceOut)
def choose(body: SplitChoiceIn, user: CurrentUser = Depends(get_current_user)) -> SplitChoiceOut:
    """Save the split the user picked. It must be one of the splits offered for their number of days."""
    with user_transaction(user.id) as conn:
        inputs = repo.read_split_inputs(conn)
        if inputs is None:
            raise HTTPException(status.HTTP_409_CONFLICT, NOT_READY)
        try:
            split = split_by_key(body.split_key)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That is not one of our workout splits.") from None
        if not fits_days(body.split_key, inputs.days_per_week):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{split.name} needs {split.training_days} training days a week, but you train {inputs.days_per_week}.",
            )
        repo.save_split_choice(conn, body.split_key)
    return SplitChoiceOut(split_key=body.split_key)
