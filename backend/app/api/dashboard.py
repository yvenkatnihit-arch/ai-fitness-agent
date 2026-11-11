"""The dashboard endpoint (Step 8.1, D-105). No model is called: this only reads saved data and adds it up."""

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.schemas.dashboard import TodayOut
from app.workflows.dashboard import today_overview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/today", response_model=TodayOut)
def today(user: CurrentUser = Depends(get_current_user)) -> TodayOut:
    """Today at a glance: what you have eaten against your targets, today's planned meals and today's workout."""
    return today_overview(user.id)
