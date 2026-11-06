"""Turn picked exercises into a week of workouts (Step 6.6c). Plain code: sets, reps, rest and weekdays come
from rules (D-049), never from the model. The result is a JSON-able "payload" saved as a pending proposal;
the same `validate_payload` check runs again when the user approves it (Step 6.6d).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.calc.exercise_filter import ExerciseOption
from app.calc.routine import MIN_SETS, prescribe
from app.calc.splits import Split

PAYLOAD_VERSION = 1
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# Which weekdays (1 = Monday) each number of training days uses: rest days spread out, weekends mostly free.
WEEK_LAYOUT: dict[int, tuple[int, ...]] = {
    1: (3,), 2: (1, 4), 3: (1, 3, 5), 4: (1, 2, 4, 5), 5: (1, 2, 3, 5, 6), 6: (1, 2, 3, 4, 5, 6),
}
MAX_EXERCISES_PER_DAY = 10
DOCTOR_NOTE = "Because of your health answers, this plan is more conservative. Please check with your doctor before starting."


@dataclass(frozen=True)
class DayPick:
    """What the picker returned for one training day (keys only)."""
    label: str
    keys: Sequence[str]


def next_monday(today: date) -> date:
    """The Monday the plan starts: today if it is a Monday, otherwise the coming one."""
    return today + timedelta(days=(7 - today.weekday()) % 7)


def build_payload(
    split: Split, day_picks: Sequence[DayPick], library: Mapping[str, ExerciseOption],
    *, level: str, goal: str, pace: str, flagged: bool, week_start: date,
) -> dict[str, Any]:
    """The workout proposal payload. `pace` must be the effective pace (health flags already applied)."""
    if len(day_picks) != split.training_days:
        raise ValueError("need one set of picks per training day")
    if split.training_days not in WEEK_LAYOUT:
        raise ValueError(f"{split.training_days} training days cannot be laid out in a week")
    weekdays = dict(zip(WEEK_LAYOUT[split.training_days], day_picks, strict=True))
    days: list[dict[str, Any]] = []
    for dow in range(1, 8):
        pick = weekdays.get(dow)
        if pick is None:
            days.append({"day_of_week": dow, "focus": "Rest", "is_rest": True, "exercises": []})
            continue
        exercises = []
        for key in pick.keys:
            ex = library[key]
            rx = prescribe(level, goal, pace, ex.movement_pattern, ex.muscle_groups, ex.name)  # type: ignore[arg-type]
            if rx is None:
                continue   # cardio/mobility: timed work is not planned yet (never invent a prescription)
            sets = max(MIN_SETS, rx.sets - 1) if flagged else rx.sets
            exercises.append({
                "exercise_key": key, "name": ex.name, "position": len(exercises) + 1, "sets": sets,
                "reps_min": rx.reps_min, "reps_max": rx.reps_max, "rest_sec": rx.rest_sec, "note": rx.note,
            })
        days.append({"day_of_week": dow, "focus": pick.label, "is_rest": False, "exercises": exercises})
    return {
        "kind": "workout_plan", "version": PAYLOAD_VERSION, "split_key": split.key, "split_name": split.name,
        "week_start": week_start.isoformat(), "level": level, "goal": goal, "doctor_note": DOCTOR_NOTE if flagged else None,
        "days": days,
    }


def summarize(payload: Mapping[str, Any]) -> str:
    """One line for the proposal card (the database allows 500 characters)."""
    trained = [d for d in payload["days"] if not d["is_rest"]]
    schedule = ", ".join(f"{WEEKDAY_NAMES[d['day_of_week'] - 1]} {d['focus']}" for d in trained)
    total = sum(len(d["exercises"]) for d in trained)
    text = f"{payload['split_name']}, {len(trained)} days a week: {schedule}. {total} exercises, starting {payload['week_start']}."
    return text if len(text) <= 500 else text[:497] + "..."


def validate_payload(payload: object, known_keys: set[str]) -> list[str]:
    """Everything wrong with a workout payload; empty means safe to save. Run before saving AND before applying."""
    if not isinstance(payload, dict) or payload.get("kind") != "workout_plan":
        return ["not a workout plan"]
    days = payload.get("days")
    if not isinstance(days, list) or [d.get("day_of_week") if isinstance(d, dict) else None for d in days] != list(range(1, 8)):
        return ["a plan needs exactly seven days, Monday to Sunday, in order"]
    problems: list[str] = []
    for day in days:
        exs = day.get("exercises")
        if not isinstance(exs, list):
            problems.append(f"day {day['day_of_week']}: exercises must be a list")
            continue
        if day.get("is_rest"):
            if exs:
                problems.append(f"day {day['day_of_week']}: a rest day has exercises")
            continue
        if not 1 <= len(exs) <= MAX_EXERCISES_PER_DAY:
            problems.append(f"day {day['day_of_week']}: needs 1 to {MAX_EXERCISES_PER_DAY} exercises, has {len(exs)}")
        keys = [e.get("exercise_key") for e in exs]
        if len(set(keys)) != len(keys):
            problems.append(f"day {day['day_of_week']}: an exercise appears twice")
        for n, e in enumerate(exs, 1):
            where = f"day {day['day_of_week']} exercise {n}"
            if e.get("exercise_key") not in known_keys:
                problems.append(f"{where}: not in the exercise library")
            if e.get("position") != n:
                problems.append(f"{where}: wrong position")
            if not (isinstance(e.get("sets"), int) and 1 <= e["sets"] <= 10):
                problems.append(f"{where}: sets must be 1 to 10")
            lo, hi = e.get("reps_min"), e.get("reps_max")
            if not (isinstance(lo, int) and isinstance(hi, int) and 1 <= lo <= hi <= 100 and lo <= 50):
                problems.append(f"{where}: bad reps range")
            if not (isinstance(e.get("rest_sec"), int) and 0 <= e["rest_sec"] <= 600):
                problems.append(f"{where}: rest must be 0 to 600 seconds")
    if not any(not d.get("is_rest") for d in days):
        problems.append("a plan needs at least one training day")
    return problems
