"""Generate a 7-day meal plan and save it as a PENDING proposal (Step 6.7d, D-067). Nothing becomes the user's meal plan
here: the user approves it first (decide_proposal.approve), which verifies every number again.

Order: read the user's data (as the user) -> week builder (model picks, code validates, solver portions) -> build the
payload -> verify it independently from the foods table -> save pending. No transaction stays open while the model thinks.
"""

from uuid import UUID

from app.calc.meal_plan_payload import build_payload, summarize, verify_payload
from app.calc.workout_plan import next_monday
from app.core.time import india_today
from app.db import admin_transaction, user_transaction
from app.db import proposals as proposals_repo
from app.db import targets as targets_repo
from app.db.meal_foods import list_pool_foods, read_meal_profile
from app.workflows.generate_workout_plan import Generated, NotReady
from app.workflows.inputs import meal_targets
from app.workflows.pick_meals import Ask, MealPlanFailed, PoolTooSmall, pick_meals

PROPOSAL_TYPE = "meal_change"
REUSE_WITHIN_SECONDS = 60   # a double-tap returns the proposal just made instead of paying for another two model calls


def generate_meal_plan(user_id: UUID, *, ask: Ask | None = None) -> Generated:
    today = india_today()
    with user_transaction(user_id) as conn:
        saved = targets_repo.read_inputs(conn)
        profile = read_meal_profile(conn)
        if saved is None or profile is None:
            raise NotReady("Please finish onboarding first.")
        recent = proposals_repo.recent_pending(conn, PROPOSAL_TYPE, REUSE_WITHIN_SECONDS)
        foods = list_pool_foods(conn)
    if recent is not None:
        return Generated(recent, reused=True)

    mt = meal_targets(saved, today)
    try:
        week = pick_meals(foods, profile.diet_type, profile.dislikes, mt.day, saved.goal_type, mt.emphasis,
                          ask=ask, user_id=user_id, cuisines=profile.cuisines)
    except (PoolTooSmall, MealPlanFailed) as error:
        raise NotReady(str(error)) from None

    payload = build_payload(week, mt.day, diet_type=profile.diet_type, goal=saved.goal_type,
                            week_start=next_monday(today), numbers_hidden=mt.numbers_hidden)
    problems = verify_payload(payload, {f.key: f for f in foods}, diet_type=profile.diet_type,
                              dislikes=profile.dislikes, targets=mt.day, cuisines=profile.cuisines)
    if problems:   # a bug on our side, never the user's fault: refuse to save rather than save something unsafe
        raise RuntimeError(f"generated meal plan failed verification: {problems[:5]}")
    with admin_transaction("save pending meal proposal") as admin:
        row = proposals_repo.replace_pending(admin, user_id, PROPOSAL_TYPE, summarize(payload), payload)
    return Generated(row, reused=False)
