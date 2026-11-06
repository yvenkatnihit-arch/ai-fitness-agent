"""The exercise-picker prompt and the parsing of its answer. No user free text goes in: only our own
exercise list, the day labels from our split catalogue, and the experience level and goal words."""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.calc.exercise_filter import ExerciseOption

SYSTEM = (
    "You are a strength coach choosing exercises for a workout plan. "
    "You may ONLY choose exercises from the list given for each day, using their exact keys. "
    "Never invent an exercise and never change a key. Do not write sets, reps, weights or any numbers. "
    "Prefer a sensible mix of movements, put big compound lifts first, and avoid choosing the same "
    "exercise on different days unless there is no other choice. "
    'Answer with JSON only, in this shape: {"days": [{"day": 1, "exercises": ["key", "key"]}]}'
)


@dataclass(frozen=True)
class DayRequest:
    number: int                              # 1-based position in the week's training days
    label: str                               # "Push", "Full body A"...
    wanted: int
    candidates: Sequence[ExerciseOption]
    problems: Sequence[str] = ()             # what was wrong with the last answer for this day (retry only)


def build_user_prompt(level: str, goal: str, days: Sequence[DayRequest]) -> str:
    lines = [f"Experience level: {level}. Goal: {goal}.", ""]
    for d in days:
        lines.append(f"Day {d.number}: {d.label}. Choose exactly {d.wanted} exercises from this list:")
        for o in d.candidates:
            lines.append(f"- {o.key} | {o.name} | {', '.join(o.muscle_groups)} | {o.movement_pattern}")
        if d.problems:
            lines.append(f"Your previous answer for this day was rejected: {'; '.join(d.problems)}. Fix this.")
        lines.append("")
    return "\n".join(lines).strip()


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_answer(text: str) -> dict[int, object]:
    """{day number: the model's list of keys}. Anything unreadable gives an empty dict (the day then falls back)."""
    try:
        data = json.loads(_FENCE.sub("", text.strip()))
    except (json.JSONDecodeError, ValueError):
        return {}
    days = data.get("days") if isinstance(data, dict) else None
    if not isinstance(days, list):
        return {}
    answer: dict[int, object] = {}
    for item in days:
        if isinstance(item, dict) and isinstance(item.get("day"), int) and "exercises" in item:
            answer[item["day"]] = item["exercises"]
    return answer
