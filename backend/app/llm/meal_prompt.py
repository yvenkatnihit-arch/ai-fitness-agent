"""The meal-planner prompt and the parsing of its answer. No user free text goes in: only our own dish list (names and
code-made tags, never raw numbers), the diet and goal words, and a code-decided emphasis."""

import json
import re
from collections.abc import Mapping, Sequence

from app.calc.meal_pool import SlotPool
from app.calc.meal_week import food_tags

SYSTEM = (
    "You are a nutrition coach planning Indian meals for one person. "
    "For each day and meal, choose ONLY from the dishes listed for that meal and role, using their exact keys. "
    "Never invent a dish and never change a key. Do not write quantities, calories or any numbers: portions are "
    "worked out separately. A role marked optional may be null. "
    "Vary the week: do not put the same protein dish or vegetable dish twice in one day, and avoid repeating a dish "
    "on back-to-back days when there is another good choice. Make each meal a sensible combination. "
    'Answer with JSON only, in this shape: {"days": [{"day": 1, "meals": {"breakfast": {"main": "key", "extra": null}}}]}'
)

EMPHASIS_TEXT = {
    "high_protein": "This person needs a lot of protein: prefer dishes tagged protein-rich wherever they make sense.",
    "low_protein": "This person must limit protein: prefer lower-protein dishes and avoid dishes tagged protein-rich.",
}


def build_user_prompt(diet_type: str, goal: str, emphasis: str | None, slots: Sequence[str],
                      pool: Mapping[str, SlotPool], days: Sequence[int],
                      feedback: Mapping[int, Sequence[str]] | None = None) -> str:
    lines = [f"Diet: {diet_type.replace('_', ' ')}. Goal: {goal.replace('_', ' ')}."]
    if emphasis in EMPHASIS_TEXT:
        lines.append(EMPHASIS_TEXT[emphasis])
    lines += ["", "Allowed dishes by meal and role:"]
    for slot in slots:
        lines.append(f"{slot}:")
        for role, foods in pool[slot].roles.items():
            required = "required" if role in pool[slot].required else "optional"
            lines.append(f"  {role} ({required}):")
            for f in foods:
                tags = ", ".join(food_tags(f))
                lines.append(f"    - {f.key} | {f.name}" + (f" | {tags}" if tags else ""))
    lines += ["", f"Plan these days: {', '.join(str(d) for d in days)}. Meals in each day: {', '.join(slots)}."]
    for day, problems in (feedback or {}).items():
        lines.append(f"Your previous answer for day {day} was rejected: {'; '.join(problems)}. Fix this.")
    return "\n".join(lines)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_answer(text: str) -> dict[int, object]:
    """{day number: that day's meals mapping}. Anything unreadable gives an empty dict (the days then fall back)."""
    try:
        data = json.loads(_FENCE.sub("", text.strip()))
    except (json.JSONDecodeError, ValueError):
        return {}
    days = data.get("days") if isinstance(data, dict) else None
    if not isinstance(days, list):
        return {}
    answer: dict[int, object] = {}
    for item in days:
        if isinstance(item, dict) and isinstance(item.get("day"), int) and "meals" in item:
            answer[item["day"]] = item["meals"]
    return answer
