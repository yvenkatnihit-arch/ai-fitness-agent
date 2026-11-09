"""Edit the active workout plan by hand (Step 6.9a, D-071). No LLM. The user's own edits apply at once, after these checks:
only library exercises the user may do, no duplicates, at most 10 a day, weekly hard-set cap, and the whole plan re-validated.

Order: read what we need as the user (injuries, level, equipment, goal) -> in ONE admin transaction lock the active plan, apply the
edit with the pure rules, validate, write it. A refusal raises EditRefused and writes nothing.
"""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from app.calc.exercise_filter import ExerciseNeeds, ExerciseOption, setting_for, why_hidden
from app.calc.targets import effective_pace
from app.calc.workout_edit import (
    EditRefused, WhyNot, add_exercise, move_day, options_for, prescription_for, remove_exercise, swap_exercise,
)
from app.db import admin_transaction, user_transaction
from app.db import exercises as exercises_repo
from app.db import targets as targets_repo
from app.db import workout_edit as repo
from app.db import workout_plans as plans_repo

NO_PLAN = "You don't have a workout plan yet. Make one first."


@dataclass(frozen=True)
class Context:
    library: dict[str, ExerciseOption]
    why_not: WhyNot
    level: str
    goal: str
    pace: str
    flagged: bool


def _context(user_id: UUID) -> Context:
    with user_transaction(user_id) as conn:
        training = exercises_repo.read_training_context(conn)
        saved = targets_repo.read_inputs(conn)
        library = {o.key: o for o in exercises_repo.list_exercises(conn)}
    if training is None or saved is None:
        raise EditRefused("Please finish onboarding first.")
    needs = ExerciseNeeds(setting_for(training.workout_location), training.level, training.injuries, training.equipment)
    pace, _ = effective_pace(saved.pace, saved.goal_type, saved.flags)   # type: ignore[arg-type]
    return Context(library, lambda key: why_hidden(library[key], needs), training.level, saved.goal_type, pace, bool(saved.flags))


def edit_workout(user_id: UUID, op: dict[str, Any]) -> str:
    """Apply one edit and return a plain-words message. Raises EditRefused (message safe to show)."""
    ctx = _context(user_id)
    known = set(ctx.library)
    kind: Literal["move_day", "swap_exercise", "remove_exercise", "add_exercise"] = op["op"]
    with admin_transaction("edit workout plan") as conn:
        found = repo.read_active_for_edit(conn, user_id)
        if found is None:
            raise EditRefused(NO_PLAN)
        _, day_ids, plan = found
        rx = {"library": ctx.library, "why_not": ctx.why_not, "level": ctx.level, "goal": ctx.goal, "pace": ctx.pace,
              "flagged": ctx.flagged, "known_keys": known}
        if kind == "move_day":
            new, message = move_day(plan, op["from_day"], op["to_day"], known)
        elif kind == "swap_exercise":
            new, message = swap_exercise(plan, op["day"], op["position"], op["exercise_key"], **rx)
        elif kind == "remove_exercise":
            new, message = remove_exercise(plan, op["day"], op["position"], ctx.library, known)
        else:
            new, message = add_exercise(plan, op["day"], op["exercise_key"], **rx)
        repo_ids = plans_repo.exercise_ids(conn)
        repo.write_plan(conn, user_id, day_ids, new, repo_ids)
    return message


def exercise_options(user_id: UUID, day: int, position: int | None) -> list[ExerciseOption]:
    """The exercises the user could pick for a swap (position given) or an add (position None) on that day."""
    ctx = _context(user_id)
    with admin_transaction("read workout plan for options") as conn:
        found = repo.read_active_for_edit(conn, user_id, lock=False)
    if found is None:
        raise EditRefused(NO_PLAN)
    sets_for = lambda o: prescription_for(o, level=ctx.level, goal=ctx.goal, pace=ctx.pace, flagged=ctx.flagged)["sets"]
    return options_for(found[2], day, position, ctx.library, ctx.why_not, sets_for)
