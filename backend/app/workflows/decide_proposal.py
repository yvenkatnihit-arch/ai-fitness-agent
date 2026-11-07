"""The user's decision on a proposal (Step 6.6d). Approving is the ONLY way a proposal changes anything.

Only workout proposals can be applied so far; the other types arrive with their own steps and are refused
here until their apply code exists (never silently marked approved without doing anything).
"""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.calc.workout_plan import next_monday, validate_payload
from app.core.time import india_today
from app.db import admin_transaction
from app.db import workout_plans as repo


class ProposalNotFound(Exception):
    """No such proposal for this user (a proposal that belongs to someone else looks exactly the same)."""


class ProposalNotPending(Exception):
    """Already approved, rejected or expired."""


class ProposalCannotBeApplied(Exception):
    """Not a type we can apply yet, or the stored plan failed its checks. str(e) is safe to show."""


def effective_week_start(planned: date, today: date) -> date:
    """If the planned Monday has already gone by (approved days later), start on the coming Monday instead."""
    this_monday = today - timedelta(days=today.weekday())
    return planned if planned >= this_monday else next_monday(today)


def approve(user_id: UUID, proposal_id: UUID) -> tuple:
    """Check, then apply, then mark approved: all in one transaction, so a failure leaves nothing half-done."""
    with admin_transaction("approve proposal") as conn:
        row = repo.lock_proposal(conn, user_id, proposal_id)
        if row is None:
            raise ProposalNotFound
        _, kind, status, payload = row
        if status != "pending":
            raise ProposalNotPending
        if kind != "workout_change":
            raise ProposalCannotBeApplied("This kind of change cannot be approved yet.")
        ids = repo.exercise_ids(conn)
        problems = validate_payload(payload, set(ids))
        if problems:
            raise ProposalCannotBeApplied("This plan did not pass our safety checks, so it was not applied. Please generate a new one.")
        week_start = effective_week_start(date.fromisoformat(payload["week_start"]), india_today())
        repo.activate_workout_plan(conn, user_id, week_start, _with_week(payload, week_start), ids)
        return repo.mark_decided(conn, user_id, proposal_id, "approved")


def reject(user_id: UUID, proposal_id: UUID) -> tuple:
    with admin_transaction("reject proposal") as conn:
        row = repo.lock_proposal(conn, user_id, proposal_id)
        if row is None:
            raise ProposalNotFound
        if row[2] != "pending":
            raise ProposalNotPending
        return repo.mark_decided(conn, user_id, proposal_id, "rejected")


def _with_week(payload: dict[str, Any], week_start: date) -> dict[str, Any]:
    return {**payload, "week_start": week_start.isoformat()}
