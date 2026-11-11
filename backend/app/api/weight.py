"""The weight log endpoints (Step 8.6, D-112). No model is called."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.auth import CurrentUser, get_current_user
from app.schemas.weight import WeightIn, WeightOut
from app.workflows import weight_log as log

router = APIRouter(prefix="/weight", tags=["weight"])


@router.get("", response_model=WeightOut)
def history(days: int = Query(default=log.DEFAULT_DAYS, ge=7, le=365), user: CurrentUser = Depends(get_current_user)) -> WeightOut:
    """The weigh-ins of the last `days` days with the trend (all numbers worked out by code)."""
    return log.read(user.id, days)


@router.post("", response_model=WeightOut)
def add(body: WeightIn, user: CurrentUser = Depends(get_current_user)) -> WeightOut:
    """Record a weigh-in (one per day: a second one the same day replaces it). Does not change the daily targets."""
    try:
        return log.record(user.id, body.weight_kg, body.measured_on)
    except log.WeightRefused as error:
        code = status.HTTP_403_FORBIDDEN if str(error) == log.HIDDEN_MESSAGE else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(code, str(error)) from None


@router.delete("/{measured_on}", status_code=status.HTTP_204_NO_CONTENT)
def remove(measured_on: date, user: CurrentUser = Depends(get_current_user)) -> Response:
    try:
        deleted = log.remove(user.id, measured_on)
    except log.WeightRefused as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from None
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There is no weight logged for that day.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
