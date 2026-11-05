from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
from app.db import targets as repo
from app.db import user_transaction
from app.schemas.targets import TargetsOut, to_targets_out

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
