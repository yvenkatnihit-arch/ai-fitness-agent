"""The AI quality page endpoint (Step 8.7, D-113). Reads only; no model is called."""

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.schemas.insights import InsightsOut
from app.workflows.ai_usage import insights_for

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/ai", response_model=InsightsOut)
def ai(days: int = Query(default=14, ge=1, le=90), user: CurrentUser = Depends(get_current_user)) -> InsightsOut:
    """Your own AI usage (calls, tokens, cost, time), the published quality results and the rules the AI cannot break."""
    return insights_for(user.id, days)
