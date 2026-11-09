from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import CurrentUser, get_current_user
from app.db import active_plan
from app.db.active_meal_plan import read_active_meal_plan
from app.db import proposals as repo
from app.db import user_transaction
from app.llm.client import LLMBusy, LLMFailed
from app.schemas.workout_edit import EditIn, EditOut, OptionsOut
from app.schemas.exercises import to_exercise_out
from app.workflows.edit_workout import EditRefused, edit_workout, exercise_options
from app.schemas.meal_plans import ActiveMealPlanOut, to_active_meal_plan
from app.schemas.plans import ActivePlanOut, ProposalListOut, ProposalOut, to_proposal_out
from app.workflows import decide_proposal as decide
from app.workflows.decide_proposal import ProposalCannotBeApplied, ProposalNotFound, ProposalNotPending
from app.workflows.generate_meal_plan import generate_meal_plan
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


def _decide(action, user: CurrentUser, proposal_id: UUID) -> ProposalOut:
    try:
        return to_proposal_out(action(user.id, proposal_id))
    except ProposalNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that proposal.") from None
    except ProposalNotPending:
        raise HTTPException(status.HTTP_409_CONFLICT, "That proposal has already been decided or has expired.") from None
    except ProposalCannotBeApplied as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None


@router.post("/proposals/{proposal_id}/approve", response_model=ProposalOut)
def approve_proposal(proposal_id: UUID, user: CurrentUser = Depends(get_current_user)) -> ProposalOut:
    """The user says yes: only now does the proposed workout become their active plan (the old one is archived)."""
    return _decide(decide.approve, user, proposal_id)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalOut)
def reject_proposal(proposal_id: UUID, user: CurrentUser = Depends(get_current_user)) -> ProposalOut:
    """The user says no: nothing else changes."""
    return _decide(decide.reject, user, proposal_id)


@router.post("/meal/generate", response_model=ProposalOut)
def generate_meal(user: CurrentUser = Depends(get_current_user)) -> ProposalOut:
    """Make a 7-day meal plan for the user's diet and targets. It is saved as a PENDING proposal: they approve it first.
    Takes about a minute (two mid-tier model calls plus the solver)."""
    try:
        return to_proposal_out(generate_meal_plan(user.id).row)
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


@router.get("/workout/active", response_model=ActivePlanOut)
def active_workout(user: CurrentUser = Depends(get_current_user)) -> ActivePlanOut:
    """The user's approved workout plan (no LLM: read from the database)."""
    with user_transaction(user.id) as conn:
        plan = active_plan.read_active_plan(conn)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't have a workout plan yet.")
    return ActivePlanOut(**plan)


@router.get("/meal/active", response_model=ActiveMealPlanOut)
def active_meal(user: CurrentUser = Depends(get_current_user)) -> ActiveMealPlanOut:
    """The user's approved meal plan (no LLM: read from the database). Numbers are removed for eating-disorder history."""
    with user_transaction(user.id) as conn:
        raw = read_active_meal_plan(conn)
    if raw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't have a meal plan yet.")
    return to_active_meal_plan(raw)


@router.post("/workout/edit", response_model=EditOut)
def edit_active_workout(body: EditIn, user: CurrentUser = Depends(get_current_user)) -> EditOut:
    """The user's own edit of their workout plan (move a day, swap, remove or add an exercise). It applies at once, but code checks it
    first: only exercises they may do, no duplicates, at most 10 a day, and the weekly hard-set cap. No LLM."""
    try:
        message = edit_workout(user.id, body.model_dump())
    except EditRefused as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    with user_transaction(user.id) as conn:
        plan = active_plan.read_active_plan(conn)
    if plan is None:   # cannot happen right after a successful edit
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't have a workout plan yet.")
    return EditOut(message=message, plan=ActivePlanOut(**plan))


@router.get("/workout/options", response_model=OptionsOut)
def workout_options(day: int = Query(ge=1, le=7), position: int | None = Query(default=None, ge=1, le=10),
                    user: CurrentUser = Depends(get_current_user)) -> OptionsOut:
    """Exercises the user could pick: for a swap (give `position`) or an add (leave it out). Only ones they may do."""
    try:
        found = exercise_options(user.id, day, position)
    except EditRefused as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    return OptionsOut(options=[to_exercise_out(o) for o in found])
