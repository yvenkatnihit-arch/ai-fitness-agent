"""How many exercises fit in the time the user has (Step 6.6f, D-057). Plain code, no LLM.

A session = warm-up + for each exercise: its sets (work time + rest after each set) + a little time to set up.
Sets and rest come from the routine rules (D-049), so a short session at a hard pace and a long one at an
easy pace both come out right. Timings are estimates; real sessions vary.
"""

from collections.abc import Sequence

from app.calc.routine import prescribe

SESSION_MINUTES = (30, 45, 60, 90)
DEFAULT_SESSION_MINUTES = 60          # used when the user has not answered (accounts made before this question)
WARMUP_MINUTES = 5
SECONDS_PER_SET = 40                  # time under load for one set (about 10 reps, or a short hold)
SETUP_SECONDS = 30                    # moving to the next exercise, setting up the weight
MIN_EXERCISES, MAX_EXERCISES = 3, 8
LEVEL_MAX_EXERCISES = {"beginner": 5, "intermediate": 7, "advanced": 8}   # more time is not more exercises for a beginner

# What a typical day looks like, in order: two big lifts, then single-muscle work, with a core exercise in the middle.
TYPICAL_DAY = ("compound", "compound", "isolation", "isolation", "core", "isolation", "compound", "isolation")
_EXAMPLE = {   # one representative exercise per kind, so the routine rules give its sets and rest
    "compound": ("squat", ("quads", "glutes"), "Squat"),
    "isolation": ("pull_vertical", ("biceps",), "Curl"),
    "core": ("core", ("abs",), "Crunch"),
}


def exercise_seconds(sets: int, rest_sec: int) -> int:
    """Time for one exercise: every set plus the rest after it, plus setup."""
    return sets * (SECONDS_PER_SET + rest_sec) + SETUP_SECONDS


def exercises_for_session(level: str, goal: str, pace: str, minutes: int | None) -> int:
    """How many exercises a training day should have. Never fewer than 3, never more than the level allows."""
    minutes = DEFAULT_SESSION_MINUTES if minutes is None else minutes
    if minutes not in SESSION_MINUTES:
        raise ValueError(f"session minutes must be one of {list(SESSION_MINUTES)}, got {minutes!r}")
    budget = (minutes - WARMUP_MINUTES) * 60
    used, count = 0, 0
    for kind in TYPICAL_DAY:
        rx = prescribe(level, goal, pace, *_EXAMPLE[kind])   # type: ignore[arg-type]
        if rx is None:
            continue   # cannot happen for these three kinds; skipping is safer than crashing
        cost = exercise_seconds(rx.sets, rx.rest_sec)
        if used + cost > budget:
            break
        used += cost
        count += 1
    return max(MIN_EXERCISES, min(count, LEVEL_MAX_EXERCISES[level], MAX_EXERCISES))


def estimate_day_minutes(exercises: Sequence[tuple[int, int]]) -> int:
    """About how long a day takes, from its real (sets, rest_sec) pairs, rounded to 5 minutes."""
    seconds = WARMUP_MINUTES * 60 + sum(exercise_seconds(sets, rest) for sets, rest in exercises)
    return int(round(seconds / 60 / 5) * 5)
