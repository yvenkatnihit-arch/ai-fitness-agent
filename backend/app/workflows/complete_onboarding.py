"""Finish onboarding: saved answers -> calculation engine -> targets saved -> onboarding marked done.

No LLM anywhere: the numbers come from app/calc (CLAUDE.md: "the LLM never does math").
"""

from uuid import UUID

from app.calc.age import age_on
from app.calc.engine import BodyProfile, Targets, calculate_targets
from app.core.time import india_today
from app.db import admin_transaction, user_transaction
from app.db import onboarding as onboarding_repo
from app.db import targets as targets_repo


class StepsMissing(onboarding_repo.OnboardingError):
    def __init__(self, steps: list[str]):
        super().__init__(f"Please finish these steps first: {', '.join(steps)}.")


def complete_onboarding(user_id: UUID) -> Targets:
    # 1. Read as the user, under RLS.
    with user_transaction(user_id) as conn:
        status = onboarding_repo.get_status(conn)
        if status.completed:
            raise onboarding_repo.AlreadyOnboarded()
        missing = [step for step in onboarding_repo.STEPS if not getattr(status, step)]
        if missing:
            raise StepsMissing(missing)
        saved = targets_repo.read_inputs(conn)
    if saved is None:  # shouldn't happen once every step is done; fail safely
        raise StepsMissing(["basics"])

    # 2. Calculate in code (Phase 1 engine).
    today = india_today()
    profile = BodyProfile(
        weight_kg=saved.weight_kg,
        height_cm=saved.height_cm,
        age_years=age_on(saved.date_of_birth, today),
        sex=saved.sex,
        activity_level=saved.activity_level,
        goal=saved.goal_type,
        screening_flags=saved.flags,
    )
    targets = calculate_targets(profile)
    inputs = {
        "weight_kg": profile.weight_kg, "height_cm": profile.height_cm, "age_years": profile.age_years,
        "sex": profile.sex, "activity_level": profile.activity_level, "goal": profile.goal,
        "screening_flags": sorted(profile.screening_flags), "calculated_on": today.isoformat(),
    }

    # 3. Save both in ONE admin transaction (calculated_targets is server-written, D-027).
    with admin_transaction("complete onboarding: save calculated targets") as conn:
        if not targets_repo.mark_onboarded(conn, user_id):
            raise onboarding_repo.AlreadyOnboarded()  # a second request got here first
        targets_repo.insert_targets(conn, user_id, saved.goal_id, targets, inputs)
    return targets
