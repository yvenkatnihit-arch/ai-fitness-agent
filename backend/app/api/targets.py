from fastapi import APIRouter, Depends, HTTPException, status

from app.calc.forecast import forecast_goal
from app.core.auth import CurrentUser, get_current_user
from app.core.time import india_today
from app.db import targets as repo
from app.db import user_transaction
from app.schemas.forecast import ForecastOut, to_forecast_out
from app.schemas.targets import TargetsOut, to_targets_out
from app.workflows.inputs import body_profile

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get("/current", response_model=TargetsOut)
def current(user: CurrentUser = Depends(get_current_user)) -> TargetsOut:
    """The user's newest daily targets (no LLM: read from the database)."""
    with user_transaction(user.id) as conn:
        row = repo.current_targets(conn)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No targets yet. Please finish onboarding.")
    kcal, protein, fat, carbs, reasons, doctor_note, habits = row
    return to_targets_out(float(kcal), float(protein), float(fat), float(carbs), reasons, doctor_note, habits)


@router.get("/forecast", response_model=ForecastOut)
def forecast(user: CurrentUser = Depends(get_current_user)) -> ForecastOut:
    """When the user might reach their target weight: an earliest / likely / latest range (no LLM: plain code)."""
    with user_transaction(user.id) as conn:
        saved = repo.read_inputs(conn)
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No forecast yet. Please finish onboarding.")
    today = india_today()
    return to_forecast_out(forecast_goal(body_profile(saved, today), saved.target_weight_kg, today))
