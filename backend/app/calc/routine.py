"""Routine rules: sets, reps and rest for an exercise, and when to add weight (Step 6.4, D-049).

Pure code. The plan generator picks WHICH exercises (from the library, by split day); this module decides
HOW MUCH of each, so the model never invents a set or rep number (CLAUDE.md: the LLM never does math).

    prescribe(level, goal, pace, exercise)  -> Prescription (sets, reps_min, reps_max, rest_sec, note)
    next_weight(...)                        -> Progression (the weight for next session, and why)

Cardio and mobility are timed, not sets and reps; they get their own rules in the plan generator.
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.calc.targets import Goal
from app.core.vocabulary import PACES, ExperienceLevel, Pace

Kind = Literal["compound", "isolation", "core", "timed"]

# Hold-type exercises are done for time, not reps: the plan stores 1 rep and the hold length in the note.
TIMED_NAME = re.compile(r"\b(plank|hold|wall sit)\b", re.IGNORECASE)
UNTIMED_PATTERNS = ("cardio", "mobility")

LEVELS = ("beginner", "intermediate", "advanced")

# Sets per exercise before pace is applied.
BASE_SETS: dict[str, dict[str, int]] = {
    "beginner":     {"compound": 2, "isolation": 2, "core": 2, "timed": 2},
    "intermediate": {"compound": 3, "isolation": 3, "core": 3, "timed": 3},
    "advanced":     {"compound": 4, "isolation": 3, "core": 3, "timed": 3},
}
MIN_SETS, MAX_SETS = 2, 5            # the plan table allows 1-10; we stay in a sensible band

# Rep ranges. Beginners learn technique, so every goal gets the same moderate range.
BEGINNER_REPS = {"compound": (8, 12), "isolation": (10, 15), "core": (10, 15)}
REPS: dict[str, dict[str, tuple[int, int]]] = {
    "muscle_gain":     {"compound": (6, 10), "isolation": (10, 15), "core": (10, 15)},
    "weight_gain":     {"compound": (6, 10), "isolation": (10, 15), "core": (10, 15)},
    "recomp":          {"compound": (8, 12), "isolation": (10, 15), "core": (10, 15)},
    "fat_loss":        {"compound": (8, 12), "isolation": (12, 15), "core": (12, 20)},
    "general_fitness": {"compound": (8, 12), "isolation": (10, 15), "core": (10, 15)},
}

# Rest in seconds. Heavy compound lifts need more; goals that want a higher heart rate rest less.
COMPOUND_REST = {"beginner": 90, "intermediate": 120, "advanced": 150}
SHORTER_REST_GOALS = ("fat_loss", "recomp", "general_fitness")
SHORTER_REST_BY = 30
ISOLATION_REST, CORE_REST, TIMED_REST = 60, 45, 45
HOLD_SECONDS = {"beginner": (20, 30), "intermediate": (30, 45), "advanced": (45, 60)}


@dataclass(frozen=True)
class Prescription:
    sets: int
    reps_min: int
    reps_max: int
    rest_sec: int
    note: str | None = None   # fits plan table's target_load_note: "Hold 30-45 seconds", "Leave 2 reps in reserve"


def exercise_kind(movement_pattern: str, muscle_groups: Sequence[str], name: str) -> Kind | None:
    """How to prescribe an exercise, or None for cardio and mobility (timed work, handled elsewhere)."""
    if movement_pattern in UNTIMED_PATTERNS:
        return None
    if TIMED_NAME.search(name):
        return "timed"
    if movement_pattern == "core":
        return "core"
    # One muscle only (curls, lateral raises, calf raises, pushdowns) is an isolation exercise.
    return "isolation" if len(set(muscle_groups)) == 1 else "compound"


def _sets(level: str, kind: Kind, pace: Pace) -> int:
    sets = BASE_SETS[level][kind]
    if pace == "slow":
        sets -= 1
    elif pace == "fast" and level != "beginner" and kind == "compound":
        sets += 1    # more volume only for experienced lifters, only on the big lifts
    return max(MIN_SETS, min(MAX_SETS, sets))


def _rest(level: str, goal: str, kind: Kind) -> int:
    if kind == "compound":
        rest = COMPOUND_REST[level]
        return rest - SHORTER_REST_BY if goal in SHORTER_REST_GOALS else rest
    return {"isolation": ISOLATION_REST, "core": CORE_REST, "timed": TIMED_REST}[kind]


def prescribe(level: ExperienceLevel, goal: Goal, pace: Pace, movement_pattern: str,
              muscle_groups: Sequence[str], name: str) -> Prescription | None:
    """Sets, reps and rest for one exercise. None for cardio and mobility.

    `pace` is the pace we actually use (after app.calc.targets.effective_pace), so people with a health
    flag never get the extra "fast" volume.
    """
    if level not in LEVELS:
        raise ValueError(f"level must be one of {list(LEVELS)}, got {level!r}")
    if goal not in REPS:
        raise ValueError(f"goal must be one of {list(REPS)}, got {goal!r}")
    if pace not in PACES:
        raise ValueError(f"pace must be one of {list(PACES)}, got {pace!r}")

    kind = exercise_kind(movement_pattern, muscle_groups, name)
    if kind is None:
        return None
    sets, rest = _sets(level, kind, pace), _rest(level, goal, kind)
    if kind == "timed":
        low, high = HOLD_SECONDS[level]
        return Prescription(sets, 1, 1, rest, f"Hold {low}-{high} seconds")
    reps = BEGINNER_REPS[kind] if level == "beginner" else REPS[goal][kind]
    return Prescription(sets, reps[0], reps[1], rest, "Stop each set with 2 good reps left in the tank")


# --- Progression ---

UPPER_BODY_STEP_KG = 2.5
LOWER_BODY_STEP_KG = 5.0
DELOAD_FRACTION = 0.10           # drop this much after two struggling sessions in a row
LOWER_BODY_PATTERNS = ("squat", "hinge", "lunge")

Action = Literal["start", "increase", "hold", "reduce"]


@dataclass(frozen=True)
class Progression:
    action: Action
    weight_kg: float | None    # next session's weight; None = bodyweight, or no history yet
    reason: str


def _round_half_kg(value: float) -> float:
    return round(value * 2) / 2


def _floor_half_kg(value: float) -> float:
    """Round DOWN to the nearest 0.5 kg: a reduction must never come out heavier than intended."""
    return math.floor(round(value * 2, 6)) / 2   # round(.., 6) first so 35.99999999 does not drop a whole step


def next_weight(last_weight_kg: float | None, history: Sequence[Sequence[int]], rx: Prescription,
                movement_pattern: str) -> Progression:
    """Double progression: keep the weight until every set reaches the top of the rep range, then add weight.

    `history` is the reps done in each set of the most recent sessions, oldest first (only the last two count).
    Two sessions in a row with a set below the bottom of the range means the weight is too heavy right now.
    We never invent a starting weight: with no history the user picks one they can lift comfortably.
    """
    if last_weight_kg is not None and not 0 <= last_weight_kg <= 500:
        raise ValueError(f"weight must be 0-500 kg, got {last_weight_kg!r}")
    for session in history:
        for reps in session:
            if isinstance(reps, bool) or not isinstance(reps, int) or not 0 <= reps <= 100:
                raise ValueError(f"reps must be whole numbers from 0 to 100, got {reps!r}")
    sessions = [s for s in history if s][-2:]
    if not sessions:
        return Progression("start", None, f"Pick a weight you can lift for {rx.reps_max} reps with 2 reps to spare.")

    last = sessions[-1]
    if all(reps >= rx.reps_max for reps in last):
        if last_weight_kg is None:
            return Progression("increase", None, "Every set reached the top of the range: make it harder (slower reps, a pause, or a harder variation).")
        step = LOWER_BODY_STEP_KG if movement_pattern in LOWER_BODY_PATTERNS else UPPER_BODY_STEP_KG
        return Progression("increase", _round_half_kg(last_weight_kg + step),
                           f"Every set reached {rx.reps_max} reps: add {step:g} kg.")
    if len(sessions) == 2 and all(min(s) < rx.reps_min for s in sessions):
        if last_weight_kg is None:
            return Progression("reduce", None, "Two tough sessions in a row: use an easier variation for a week.")
        return Progression("reduce", _floor_half_kg(last_weight_kg * (1 - DELOAD_FRACTION)),
                           f"Two sessions in a row below {rx.reps_min} reps: drop the weight by 10% and build back up.")
    return Progression("hold", last_weight_kg, f"Keep the weight and add reps until every set reaches {rx.reps_max}.")
