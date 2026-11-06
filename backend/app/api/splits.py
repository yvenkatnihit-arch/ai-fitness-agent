from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.calc.splits import recommend_splits
from app.core.auth import CurrentUser, get_current_user
from app.db import splits as repo
from app.db import user_transaction
from app.schemas.splits import SplitRecommendationsOut, to_recommendation_out

router = APIRouter(prefix="/splits", tags=["splits"])


@router.get("/recommend", response_model=SplitRecommendationsOut)
def recommend(
    days: Annotated[int | None, Query(ge=1, le=7, description="Try a different number of days a week")] = None,
    user: CurrentUser = Depends(get_current_user),
) -> SplitRecommendationsOut:
    """Workout splits that fit this user's days, level and goal, best first (no LLM: plain rules)."""
    with user_transaction(user.id) as conn:
        inputs = repo.read_split_inputs(conn)
    if inputs is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Please finish the goal and training steps of onboarding first.")
    chosen_days = days or inputs.days_per_week
    recommendations = recommend_splits(chosen_days, inputs.level, inputs.goal)
    return SplitRecommendationsOut(
        days_per_week=chosen_days, level=inputs.level, goal=inputs.goal,
        recommendations=[to_recommendation_out(r) for r in recommendations],
    )
