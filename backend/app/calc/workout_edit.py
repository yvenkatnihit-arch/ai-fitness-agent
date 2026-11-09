"""Editing the active workout plan by hand (Step 6.9a, D-071). Plain code: no database, no LLM.

These are the USER'S OWN edits, so they apply at once (no approval step), but every one is checked here first: only library
exercises the user may do (injuries, level, place, equipment), no duplicates in a day, at most 10 exercises a day, and no
muscle pushed past the weekly hard-set cap. Each function takes the plan as a payload-shaped dict (the same shape the
generator makes) and returns a NEW plan plus a plain-words message, or raises EditRefused (message safe to show).
"""

import copy
from collections.abc import Callable, Mapping
from typing import Any

from app.calc.exercise_filter import ExerciseOption
from app.calc.routine import MIN_SETS, prescribe
from app.calc.session_time import estimate_day_minutes
from app.calc.workout_plan import MAX_EXERCISES_PER_DAY, WEEKDAY_NAMES, validate_payload
from app.safety.safety_config import MAX_WEEKLY_SETS_PER_MUSCLE


class EditRefused(Exception):
    """The edit is not allowed. str(e) is safe to show the user."""


# "why_hidden" reasons from app.calc.exercise_filter, in friendly words.
def friendly_reason(reason: str) -> str:
    if reason.startswith("injury:"):
        return f"it could aggravate your {reason.removeprefix('injury:').strip().replace('_', ' ')}"
    if reason.startswith("too hard"):
        return "it is harder than your experience level"
    if reason.startswith("needs equipment"):
        return f"you do not have the equipment ({reason.removeprefix('needs equipment:').strip().replace('_', ' ')})"
    return "it does not suit where you train"


WhyNot = Callable[[str], str | None]   # exercise key -> why this user may not do it, or None when it is fine


def _day(plan: Mapping[str, Any], dow: int) -> dict[str, Any]:
    if not isinstance(dow, int) or not 1 <= dow <= 7:
        raise EditRefused("Pick a day from Monday to Sunday.")
    return next(d for d in plan["days"] if d["day_of_week"] == dow)


def _name(dow: int) -> str:
    return {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday",
            "Sun": "Sunday"}[WEEKDAY_NAMES[dow - 1]]


def _renumber(day: dict[str, Any]) -> None:
    for n, e in enumerate(day["exercises"], 1):
        e["position"] = n


def _finish(plan: dict[str, Any], known_keys: set[str]) -> dict[str, Any]:
    """Recompute each day's length and re-validate the WHOLE plan. A failure here is our bug, never the user's fault."""
    for day in plan["days"]:
        day["minutes"] = None if day["is_rest"] else estimate_day_minutes([(e["sets"], e["rest_sec"]) for e in day["exercises"]])
    problems = validate_payload(plan, known_keys)
    if problems:
        raise RuntimeError(f"edited workout plan failed validation: {problems[:5]}")
    return plan


def weekly_sets(plan: Mapping[str, Any], library: Mapping[str, ExerciseOption]) -> dict[str, int]:
    """Hard sets per muscle over the week. Each exercise counts for its MAIN muscle (the first one listed). Counting every muscle an
    exercise touches double-counts rows, pulldowns and curls, and a normal pull day would already exceed the cap."""
    totals: dict[str, int] = {}
    for day in plan["days"]:
        for e in day["exercises"]:
            main = library[e["exercise_key"]].muscle_groups[0]
            totals[main] = totals.get(main, 0) + e["sets"]
    return totals


def prescription_for(ex: ExerciseOption, *, level: str, goal: str, pace: str, flagged: bool) -> dict[str, Any]:
    """Sets, reps, rest and note for an exercise, from the same rules as the generator (D-049)."""
    rx = prescribe(level, goal, pace, ex.movement_pattern, ex.muscle_groups, ex.name)  # type: ignore[arg-type]
    if rx is None:
        raise EditRefused(f"{ex.name} is cardio or mobility work, which workout plans do not include yet.")
    return {"sets": max(MIN_SETS, rx.sets - 1) if flagged else rx.sets, "reps_min": rx.reps_min, "reps_max": rx.reps_max,
            "rest_sec": rx.rest_sec, "note": rx.note}


def _check_allowed(key: str, library: Mapping[str, ExerciseOption], why_not: WhyNot) -> ExerciseOption:
    ex = library.get(key)
    if ex is None or ex.review_status == "blocked":
        raise EditRefused("That exercise is not in our library.")
    reason = why_not(key)
    if reason is not None:
        raise EditRefused(f"{ex.name} is not suitable for you: {friendly_reason(reason)}.")
    return ex


def _check_weekly_cap(before: Mapping[str, int], after: Mapping[str, int]) -> None:
    """An edit may not push a muscle past the weekly cap. A plan already over it may still be reduced, never increased."""
    for muscle, total in after.items():
        if total > MAX_WEEKLY_SETS_PER_MUSCLE and total > before.get(muscle, 0):
            raise EditRefused(f"That would put more than {MAX_WEEKLY_SETS_PER_MUSCLE} hard sets a week on {muscle.replace('_', ' ')}, "
                              "which is more than we allow.")


def move_day(plan: Mapping[str, Any], from_day: int, to_day: int, known_keys: set[str]) -> tuple[dict[str, Any], str]:
    """Move a training day to another weekday. Onto a rest day it moves; onto another training day the two swap."""
    new = copy.deepcopy(dict(plan))
    a, b = _day(new, from_day), _day(new, to_day)
    if from_day == to_day:
        raise EditRefused("That is already the day.")
    if a["is_rest"]:
        raise EditRefused(f"{_name(from_day)} is a rest day. Pick one of your training days to move.")
    for key in ("focus", "is_rest", "exercises"):
        a[key], b[key] = b[key], a[key]
    message = (f"Moved {b['focus']} from {_name(from_day)} to {_name(to_day)}." if a["is_rest"]
               else f"Swapped {b['focus']} ({_name(from_day)} to {_name(to_day)}) with {a['focus']}.")
    return _finish(new, known_keys), message


def swap_exercise(plan: Mapping[str, Any], day: int, position: int, new_key: str, *, library: Mapping[str, ExerciseOption],
                  why_not: WhyNot, level: str, goal: str, pace: str, flagged: bool, known_keys: set[str]) -> tuple[dict[str, Any], str]:
    """Replace one exercise with another the user may do that trains the same muscles or uses the same movement."""
    new = copy.deepcopy(dict(plan))
    d = _day(new, day)
    if d["is_rest"] or not 1 <= position <= len(d["exercises"]):
        raise EditRefused("There is no such exercise on that day.")
    old = d["exercises"][position - 1]
    replacement = _check_allowed(new_key, library, why_not)
    if new_key in {e["exercise_key"] for e in d["exercises"]}:
        raise EditRefused(f"{replacement.name} is already on {_name(day)}.")
    previous = library[old["exercise_key"]]
    if replacement.movement_pattern != previous.movement_pattern and not set(replacement.muscle_groups) & set(previous.muscle_groups):
        raise EditRefused(f"Pick an exercise that trains the same muscles as {previous.name}.")
    before = weekly_sets(new, library)
    d["exercises"][position - 1] = {"exercise_key": new_key, "name": replacement.name, "position": position,
                                    **prescription_for(replacement, level=level, goal=goal, pace=pace, flagged=flagged)}
    _check_weekly_cap(before, weekly_sets(new, library))
    return _finish(new, known_keys), f"Swapped {previous.name} for {replacement.name} on {_name(day)}."


def remove_exercise(plan: Mapping[str, Any], day: int, position: int, library: Mapping[str, ExerciseOption],
                    known_keys: set[str]) -> tuple[dict[str, Any], str]:
    new = copy.deepcopy(dict(plan))
    d = _day(new, day)
    if d["is_rest"] or not 1 <= position <= len(d["exercises"]):
        raise EditRefused("There is no such exercise on that day.")
    if len(d["exercises"]) == 1:
        raise EditRefused("A training day needs at least one exercise. Move the day to make it a rest day instead.")
    removed = d["exercises"].pop(position - 1)
    _renumber(d)
    return _finish(new, known_keys), f"Removed {library[removed['exercise_key']].name} from {_name(day)}."


def add_exercise(plan: Mapping[str, Any], day: int, new_key: str, *, library: Mapping[str, ExerciseOption], why_not: WhyNot,
                 level: str, goal: str, pace: str, flagged: bool, known_keys: set[str]) -> tuple[dict[str, Any], str]:
    new = copy.deepcopy(dict(plan))
    d = _day(new, day)
    if d["is_rest"]:
        raise EditRefused(f"{_name(day)} is a rest day. Move a training day there first.")
    ex = _check_allowed(new_key, library, why_not)
    if new_key in {e["exercise_key"] for e in d["exercises"]}:
        raise EditRefused(f"{ex.name} is already on {_name(day)}.")
    if len(d["exercises"]) >= MAX_EXERCISES_PER_DAY:
        raise EditRefused(f"A day can have at most {MAX_EXERCISES_PER_DAY} exercises.")
    before = weekly_sets(new, library)
    d["exercises"].append({"exercise_key": new_key, "name": ex.name, "position": len(d["exercises"]) + 1,
                           **prescription_for(ex, level=level, goal=goal, pace=pace, flagged=flagged)})
    _check_weekly_cap(before, weekly_sets(new, library))
    return _finish(new, known_keys), f"Added {ex.name} to {_name(day)}."


def options_for(plan: Mapping[str, Any], day: int, position: int | None, library: Mapping[str, ExerciseOption],
                why_not: WhyNot, sets_for: Callable[[ExerciseOption], int] | None = None) -> list[ExerciseOption]:
    """The exercises the user could pick: for a swap, ones that fit the old exercise; for an add, ones that train a muscle that
    day already trains. Only allowed ones, none already on the day, never cardio or mobility. With `sets_for` (how many sets an
    exercise would get) the ones that would break the weekly cap are left out, so every choice offered will be accepted."""
    d = _day(plan, day)
    if d["is_rest"]:
        return []
    on_day = {e["exercise_key"] for e in d["exercises"]}
    if position is not None:
        if not 1 <= position <= len(d["exercises"]):
            raise EditRefused("There is no such exercise on that day.")
        old = library[d["exercises"][position - 1]["exercise_key"]]
        fits = lambda o: o.movement_pattern == old.movement_pattern or bool(set(o.muscle_groups) & set(old.muscle_groups))
    else:
        muscles = {m for e in d["exercises"] for m in library[e["exercise_key"]].muscle_groups}
        fits = lambda o: bool(set(o.muscle_groups) & muscles)
    base = weekly_sets(plan, library)
    if position is not None:   # a swap frees the old exercise's sets first
        old_ex, old_sets = library[d["exercises"][position - 1]["exercise_key"]], d["exercises"][position - 1]["sets"]
        base[old_ex.muscle_groups[0]] = base.get(old_ex.muscle_groups[0], 0) - old_sets

    def cap_ok(o: ExerciseOption) -> bool:
        if sets_for is None:
            return True
        main = o.muscle_groups[0]
        total = base.get(main, 0) + sets_for(o)
        return total <= MAX_WEEKLY_SETS_PER_MUSCLE or total <= weekly_sets(plan, library).get(main, 0)

    out = [o for o in library.values() if o.key not in on_day and o.review_status != "blocked" and o.movement_pattern not in ("cardio", "mobility")
           and why_not(o.key) is None and fits(o) and cap_ok(o)]
    return sorted(out, key=lambda o: (o.difficulty, o.name))
