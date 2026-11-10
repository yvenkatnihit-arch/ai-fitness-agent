"""Keep a generated workout plan inside the weekly hard-set cap (Step 7.9a, D-087). Plain code, no model.

`MAX_WEEKLY_SETS_PER_MUSCLE` (safety_config) was only enforced for edits and focus sets; the plan eval found long splits and long sessions
well above it (56 back sets a week on a 6-day push/pull/legs plan). Each exercise counts for its MAIN muscle (the first one listed),
the same rule the edit screen uses. For a muscle over the cap this trims, in this order:

  1. sets: one set at a time from the exercise of that muscle with the MOST sets (ties: the later exercise in the day, then the later
     day), never below MIN_SETS;
  2. exercises, only when every exercise of the muscle is already at MIN_SETS: the lowest-priority one (the last in its day) from the
     day with the most exercises for that muscle, never leaving a day with fewer than MIN_DAY_EXERCISES.

If the cap cannot be met without breaking those floors, the muscle is reported as `unresolved` (never hidden).
"""

from collections.abc import Mapping, MutableSequence
from dataclasses import dataclass, field
from typing import Any

from app.calc.day_picks import MIN_DAY_EXERCISES
from app.calc.routine import MIN_SETS
from app.safety.safety_config import MAX_WEEKLY_SETS_PER_MUSCLE


@dataclass
class Trim:
    sets_removed: int = 0
    exercises_removed: int = 0
    by_muscle: dict[str, int] = field(default_factory=dict)   # sets removed per muscle (removed exercises count their sets)
    unresolved: list[str] = field(default_factory=list)       # muscles still above the cap

    @property
    def changed(self) -> bool:
        return bool(self.sets_removed or self.exercises_removed)


def _totals(days: MutableSequence[dict[str, Any]], main_muscle: Mapping[str, str]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for d in days:
        for e in d["exercises"]:
            m = main_muscle[e["exercise_key"]]
            totals[m] = totals.get(m, 0) + e["sets"]
    return totals


def enforce_weekly_cap(days: MutableSequence[dict[str, Any]], main_muscle: Mapping[str, str], *, cap: int = MAX_WEEKLY_SETS_PER_MUSCLE,
                       min_sets: int = MIN_SETS, min_day_exercises: int = MIN_DAY_EXERCISES) -> Trim:
    """Trim `days` IN PLACE (rest days are skipped) so no muscle is above `cap`. Returns what was done."""
    trim = Trim()
    over = {m: n for m, n in _totals(days, main_muscle).items() if n > cap}
    for muscle in sorted(over, key=lambda m: (-over[m], m)):           # biggest overage first, stable
        while _totals(days, main_muscle).get(muscle, 0) > cap:
            candidates = [(e["sets"], e["position"], di, e) for di, d in enumerate(days) if not d["is_rest"] for e in d["exercises"]
                          if main_muscle[e["exercise_key"]] == muscle and e["sets"] > min_sets]
            if candidates:                                               # step 1: take a set from the heaviest exercise
                _, _, _, e = max(candidates, key=lambda c: (c[0], c[1], c[2]))
                e["sets"] -= 1
                trim.sets_removed += 1
                trim.by_muscle[muscle] = trim.by_muscle.get(muscle, 0) + 1
                continue
            removable = [(sum(main_muscle[x["exercise_key"]] == muscle for x in d["exercises"]), di) for di, d in enumerate(days)
                         if not d["is_rest"] and len(d["exercises"]) > min_day_exercises
                         and any(main_muscle[x["exercise_key"]] == muscle for x in d["exercises"])]
            if not removable:                                            # step 2 impossible without breaking a floor
                trim.unresolved.append(muscle)
                break
            _, di = max(removable)                                       # the day with the most work for this muscle (later day on a tie)
            d = days[di]
            idx = max(i for i, x in enumerate(d["exercises"]) if main_muscle[x["exercise_key"]] == muscle)   # its last (lowest priority)
            gone = d["exercises"].pop(idx)
            for n, x in enumerate(d["exercises"], 1):
                x["position"] = n
            trim.exercises_removed += 1
            trim.sets_removed += gone["sets"]
            trim.by_muscle[muscle] = trim.by_muscle.get(muscle, 0) + gone["sets"]
    return trim
