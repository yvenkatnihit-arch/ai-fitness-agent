"""Choose the exercises for every training day of a split (Step 6.6b).

The model picks keys from each day's allowed list; code checks them (app.calc.day_picks). A day that fails
is re-asked once (only that day), and if it still fails, code picks for it. So the result is ALWAYS valid.
Sets, reps and rest are NOT decided here: that is app.calc.routine (Step 6.6c).
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.calc.day_picks import (
    MIN_DAY_EXERCISES, day_candidates, fallback_picks, order_picks, validate_picks, wanted_count,
)
from app.calc.exercise_filter import ExerciseOption
from app.calc.splits import Split
from app.llm.client import LLMResult, call_llm
from app.llm.picker_prompt import SYSTEM, DayRequest, build_user_prompt, parse_answer

logger = logging.getLogger(__name__)

MAX_TOKENS = 4000      # generous: Gemini's own reasoning tokens count toward this limit
Ask = Callable[[str], LLMResult]   # user prompt -> model answer; tests pass a fake


@dataclass(frozen=True)
class DayPicks:
    label: str
    keys: tuple[str, ...]
    source: Literal["model", "fallback", "none"]   # "none": too few allowed exercises fit this day to make a workout
    note: str | None = None


def _default_ask(user_id: UUID | None) -> Ask:
    def ask(prompt: str) -> LLMResult:
        return call_llm("mid", [("system", SYSTEM), ("human", prompt)], flow="plan_generation",
                        node="exercise_picker", max_tokens=MAX_TOKENS, user_id=user_id,
                        temperature=0.0, json_mode=True)   # temperature 0: the same inputs give the same plan (D-052)
    return ask


def pick_exercises(
    split: Split, allowed: Sequence[ExerciseOption], level: str, goal: str,
    *, ask: Ask | None = None, user_id: UUID | None = None,
) -> list[DayPicks]:
    """One DayPicks per training day, in the split's order. `allowed` must already be filtered for this user."""
    ask = ask or _default_ask(user_id)
    cands = [day_candidates(d, allowed) for d in split.days]
    wanted = [wanted_count(level, c) for c in cands]
    results: dict[int, DayPicks] = {}
    pending = [i for i, c in enumerate(cands) if len(c) >= MIN_DAY_EXERCISES]
    for i, c in enumerate(cands):
        if len(c) < MIN_DAY_EXERCISES:
            results[i] = DayPicks(
                split.days[i].label, (), "none",
                f"Only {len(c)} exercise(s) fit this day with your equipment and limits; a workout needs at least {MIN_DAY_EXERCISES}.",
            )
    problems: dict[int, list[str]] = {}

    for attempt in range(2):
        if not pending:
            break
        requests = [DayRequest(i + 1, split.days[i].label, wanted[i], cands[i], problems.get(i, ())) for i in pending]
        try:
            answer = parse_answer(ask(build_user_prompt(level, goal, requests)).text)
        except Exception:  # noqa: BLE001 - LLMBusy/LLMFailed: the whole plan still works, via the fallback
            logger.warning("exercise picker call failed; using code picks for %d day(s)", len(pending))
            break
        still: list[int] = []
        for i in pending:
            keys = answer.get(i + 1)
            found = validate_picks(keys, cands[i], wanted[i]) if keys is not None else ["this day was missing"]
            if found:
                problems[i] = found
                still.append(i)
            else:
                results[i] = DayPicks(split.days[i].label, tuple(order_picks(keys, cands[i])), "model")  # type: ignore[arg-type]
        pending = still

    used: list[str] = [k for r in results.values() for k in r.keys]
    for i in pending:
        keys = fallback_picks(cands[i], wanted[i], used)
        used.extend(keys)
        results[i] = DayPicks(split.days[i].label, tuple(keys), "fallback", "; ".join(problems.get(i, ["model unavailable"])))
    return [results[i] for i in range(len(split.days))]
