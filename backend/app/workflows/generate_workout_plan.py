"""Generate a workout plan and save it as a PENDING proposal (Step 6.6c). Nothing becomes the user's plan here:
the user approves it first (Step 6.6d).

Order of work: read the user's data (as the user) -> filter the library (code) -> model picks exercises
(code validates) -> routine rules set the numbers (code) -> validate the whole payload (code) -> save pending.
No database transaction stays open while the model thinks.
"""

from dataclasses import dataclass
from uuid import UUID

from app.calc.exercise_filter import ExerciseNeeds, filter_exercises, setting_for
from app.calc.session_time import exercises_for_session
from app.calc.splits import fits_days, split_by_key
from app.calc.targets import effective_pace
from app.calc.workout_plan import DayPick, build_payload, next_monday, summarize, validate_payload
from app.core.time import india_today
from app.db import admin_transaction, user_transaction
from app.db import exercises as exercises_repo
from app.db import proposals as proposals_repo
from app.db import splits as splits_repo
from app.db import targets as targets_repo
from app.workflows.pick_exercises import Ask, pick_exercises

REUSE_WITHIN_SECONDS = 60   # a double-tap returns the proposal just made instead of paying for a second model call


class NotReady(Exception):
    """The user cannot get a plan yet. str(e) is safe to show them."""


@dataclass(frozen=True)
class Generated:
    row: tuple
    reused: bool


def generate_workout_plan(user_id: UUID, *, ask: Ask | None = None) -> Generated:
    with user_transaction(user_id) as conn:
        training = exercises_repo.read_training_context(conn)
        split_inputs = splits_repo.read_split_inputs(conn)
        saved = targets_repo.read_inputs(conn)
        if training is None or split_inputs is None or saved is None:
            raise NotReady("Please finish onboarding first.")
        if not split_inputs.chosen_key:
            raise NotReady("Please choose a workout split first.")
        if not fits_days(split_inputs.chosen_key, split_inputs.days_per_week):
            raise NotReady("Your chosen split no longer matches your training days. Please choose a split again.")
        recent = proposals_repo.recent_pending_workout(conn, split_inputs.chosen_key, REUSE_WITHIN_SECONDS)
        library = exercises_repo.list_exercises(conn)
    if recent is not None:
        return Generated(recent, reused=True)

    split = split_by_key(split_inputs.chosen_key)
    needs = ExerciseNeeds(setting_for(training.workout_location), training.level, training.injuries, training.equipment)
    allowed = filter_exercises(library, needs)
    pace, _ = effective_pace(saved.pace, saved.goal_type, saved.flags)   # type: ignore[arg-type]
    per_day = exercises_for_session(training.level, split_inputs.goal, pace, training.session_minutes)
    picks = pick_exercises(split, allowed, training.level, split_inputs.goal, per_day=per_day, ask=ask, user_id=user_id)

    empty = [p.label for p in picks if p.source == "none"]
    if empty:
        raise NotReady(
            f"With your equipment and limits there are not enough safe exercises for: {', '.join(empty)}. "
            "Try a different split, or add equipment in your profile."
        )

    by_key = {o.key: o for o in library}
    payload = build_payload(
        split, [DayPick(p.label, p.keys) for p in picks], by_key,
        level=training.level, goal=split_inputs.goal, pace=pace, flagged=bool(saved.flags), week_start=next_monday(india_today()),
    )
    problems = validate_payload(payload, set(by_key))
    if problems:   # a bug on our side, never the user's fault: refuse to save rather than save something unsafe
        raise RuntimeError(f"generated workout plan failed validation: {problems}")
    payload["pick_sources"] = [p.source for p in picks]   # which days the model chose and which code chose (for us, not shown)

    with admin_transaction("save pending workout proposal") as admin:
        row = proposals_repo.replace_pending_workout(admin, user_id, summarize(payload), payload)
    return Generated(row, reused=False)
