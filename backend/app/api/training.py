from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.calc.focus import check_focus
from app.core.auth import CurrentUser, get_current_user
from app.core.vocabulary import FOCUS_AREAS, MAX_FOCUS_AREAS
from app.db import user_transaction

router = APIRouter(prefix="/training", tags=["training"])


class FocusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    focus_areas: list[str]


class FocusOut(BaseModel):
    focus_areas: list[str]
    options: list[str] = list(FOCUS_AREAS)
    max_areas: int = MAX_FOCUS_AREAS


@router.get("/focus-areas", response_model=FocusOut)
def get_focus(user: CurrentUser = Depends(get_current_user)) -> FocusOut:
    """The muscles this user wants to bring up (no LLM)."""
    with user_transaction(user.id) as conn:
        row = conn.execute("select focus_areas from public.profiles where id = auth.uid()").fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Please finish onboarding first.")
    return FocusOut(focus_areas=list(row[0]))


@router.put("/focus-areas", response_model=FocusOut)
def set_focus(body: FocusIn, user: CurrentUser = Depends(get_current_user)) -> FocusOut:
    """Choose up to two muscles to bring up. Takes effect the next time a workout plan is generated."""
    try:
        areas = check_focus(body.focus_areas)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    with user_transaction(user.id) as conn:
        row = conn.execute(
            "update public.profiles set focus_areas = %s where id = auth.uid() returning focus_areas", (areas,)
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Please finish onboarding first.")
    return FocusOut(focus_areas=list(row[0]))
