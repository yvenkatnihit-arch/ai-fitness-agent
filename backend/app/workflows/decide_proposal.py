"""The user's decision on a proposal (Steps 6.6d, 6.7d). Approving is the ONLY way a proposal changes anything.

Workout and meal proposals can be applied so far; the other types arrive with their own steps and are refused
here until their apply code exists (never silently marked approved without doing anything).
"""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.calc.meal_plan_payload import verify_payload
from app.calc.portions import Per100g, nutrition_for
from app.calc.workout_plan import next_monday, validate_payload
from app.core.time import india_today
from app.db import admin_transaction, user_transaction
from app.db import meal_plans as meal_repo
from app.db import targets as targets_repo
from app.db import workout_plans as repo
from app.db.meal_foods import MealProfile, list_pool_foods, read_meal_profile
from app.workflows.inputs import MealTargets, meal_targets


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


def _kind_of(user_id: UUID, proposal_id: UUID) -> str | None:
    """The proposal's type if it is THIS user's (read under RLS), else None."""
    with user_transaction(user_id) as conn:
        row = conn.execute("select type from public.plan_proposals where id = %s", (proposal_id,)).fetchone()
    return row[0] if row else None


def _meal_context(user_id: UUID) -> tuple[MealTargets, MealProfile]:
    """What the meal plan is re-checked against: the user's targets and diet as saved TODAY (not as the proposal claims)."""
    with user_transaction(user_id) as conn:
        saved = targets_repo.read_inputs(conn)
        profile = read_meal_profile(conn)
    if saved is None or profile is None:
        raise ProposalCannotBeApplied("Please finish onboarding first.")
    return meal_targets(saved, india_today()), profile


def approve(user_id: UUID, proposal_id: UUID) -> tuple:
    """Check, then apply, then mark approved: all in one transaction, so a failure leaves nothing half-done."""
    kind = _kind_of(user_id, proposal_id)
    if kind is None:
        raise ProposalNotFound
    meal = _meal_context(user_id) if kind == "meal_change" else None
    with admin_transaction("approve proposal") as conn:
        row = repo.lock_proposal(conn, user_id, proposal_id)
        if row is None:
            raise ProposalNotFound
        _, kind, status, payload = row
        if status != "pending":
            raise ProposalNotPending
        if kind == "meal_change":
            if meal is None:   # cannot happen: the context is loaded whenever the type is meal_change
                raise ProposalCannotBeApplied("Please try again.")
            _apply_meal(conn, user_id, payload, *meal)
            return repo.mark_decided(conn, user_id, proposal_id, "approved")
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


def _apply_meal(conn, user_id: UUID, payload: dict[str, Any], mt: MealTargets, profile: MealProfile) -> None:
    """Verify the meal plan against the foods table and TODAY's targets, then write it with code-computed nutrition."""
    foods = {f.key: f for f in list_pool_foods(conn)}
    problems = verify_payload(payload, foods, diet_type=profile.diet_type, dislikes=profile.dislikes, targets=mt.day)
    if problems:
        raise ProposalCannotBeApplied("This meal plan did not pass our safety checks, so it was not applied. Please generate a new one.")
    week_start = effective_week_start(date.fromisoformat(payload["week_start"]), india_today())
    rows = []
    for day in payload["days"]:
        for item in day["items"]:
            food = foods[item["food_key"]]
            n = nutrition_for(float(item["grams"]), Per100g(food.kcal, food.protein_g, food.carbs_g, food.fat_g))
            rows.append(meal_repo.ItemRow(day["day_of_week"], item["slot"], item["position"], food.id, float(item["grams"]),
                                          item["unit"], item["quantity"], n.kcal, n.protein_g, n.carbs_g, n.fat_g))
    meal_repo.activate_meal_plan(conn, user_id, week_start, rows, meal_repo.latest_targets_id(conn, user_id))


def _with_week(payload: dict[str, Any], week_start: date) -> dict[str, Any]:
    return {**payload, "week_start": week_start.isoformat()}
