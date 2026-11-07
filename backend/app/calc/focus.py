"""Focus areas: bring up to two muscles up (Step 6.6g, D-060). Plain code; the model never decides volume.

What a focus muscle gets, only for users with no health flag (flagged plans stay conservative):
  - its days get one more exercise (`day_wanted`),
  - each exercise that trains it gets one more set, while the muscle's weekly total stays within
    MAX_WEEKLY_SETS_PER_MUSCLE and the exercise stays within MAX_SETS (`add_focus_sets`).
"""

from collections import Counter
from collections.abc import Collection, Mapping, MutableSequence
from typing import Any

from app.calc.routine import MAX_SETS
from app.calc.session_time import MAX_EXERCISES
from app.calc.splits import SplitDay
from app.core.vocabulary import FOCUS_AREAS, MAX_FOCUS_AREAS
from app.safety.safety_config import MAX_WEEKLY_SETS_PER_MUSCLE


def check_focus(areas: Collection[str]) -> list[str]:
    """The focus list cleaned up (no repeats, original order), or ValueError if it is not allowed."""
    unique = list(dict.fromkeys(areas))
    unknown = [a for a in unique if a not in FOCUS_AREAS]
    if unknown:
        raise ValueError(f"unknown focus area(s): {unknown}")
    if len(unique) > MAX_FOCUS_AREAS:
        raise ValueError(f"pick at most {MAX_FOCUS_AREAS} focus areas")
    return unique


def day_wanted(per_day: int, day: SplitDay, focus: Collection[str]) -> int:
    """Exercises for this day: one more when the day trains a focus muscle (never above the overall maximum)."""
    return min(per_day + 1, MAX_EXERCISES) if set(day.muscles) & set(focus) else per_day


def add_focus_sets(days: MutableSequence[dict[str, Any]], muscles_of: Mapping[str, Collection[str]],
                   focus: Collection[str]) -> int:
    """Give each focus-muscle exercise one more set, in week order, while every limit holds. Returns sets added.

    `days` are plan-payload days (exercises carry `exercise_key` and `sets`); `muscles_of[key]` is what the
    exercise trains. An exercise only gets the set if EVERY focus muscle it trains stays within the weekly cap.
    """
    focus = set(focus)
    if not focus:
        return 0
    weekly = Counter[str]()
    for day in days:
        for e in day["exercises"]:
            for m in focus & set(muscles_of[e["exercise_key"]]):
                weekly[m] += e["sets"]
    added = 0
    for day in days:
        for e in day["exercises"]:
            hit = focus & set(muscles_of[e["exercise_key"]])
            if hit and e["sets"] < MAX_SETS and all(weekly[m] + 1 <= MAX_WEEKLY_SETS_PER_MUSCLE for m in hit):
                e["sets"] += 1
                for m in hit:
                    weekly[m] += 1
                added += 1
    return added
