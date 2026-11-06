from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
from app.db import proposals as repo
from app.db import user_transaction
from app.llm.client import LLMBusy, LLMFailed
from app.schemas.plans import ProposalListOut, ProposalOut, to_proposal_out
from app.workflows.generate_workout_plan import NotReady, generate_workout_plan

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/workout/generate", response_model=ProposalOut)
def generate_workout(user: CurrentUser = Depends(get_current_user)) -> ProposalOut:
    """Make a workout plan from the user's chosen split. It is saved as a PENDING proposal, not as their plan:
    they approve it first. Uses the mid-tier model once (plus a retry for any day that fails the checks)."""
    try:
        return to_proposal_out(generate_workout_plan(user.id).row)
    except NotReady as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    except LLMBusy as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from None
    except LLMFailed as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from None


@router.get("/proposals/pending", response_model=ProposalListOut)
def pending(user: CurrentUser = Depends(get_current_user)) -> ProposalListOut:
    """Changes waiting for the user's approval (no LLM: read from the database)."""
    with user_transaction(user.id) as conn:
        rows = repo.list_pending(conn)
    return ProposalListOut(proposals=[to_proposal_out(r) for r in rows])
