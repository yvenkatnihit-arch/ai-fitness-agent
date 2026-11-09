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
    EXERCISES_PER_DAY, MIN_DAY_EXERCISES, day_candidates, fallback_picks, order_picks, pattern_cap, validate_picks, wanted_count,
)
from app.calc.focus import day_wanted
from app.calc.exercise_filter import ExerciseOption
from app.calc.splits import Split
from app.llm.client import LLMResult, call_llm
from app.llm.picker_prompt import SYSTEM, DayRequest, build_user_prompt, parse_answer

logger = logging.getLogger(__name__)

MAX_TOKENS = 4000      # generous: Gemini's own reasoning tokens count toward this limit
Ask = Callable[[str], LLMResult]   # user prompt -> model answer; tests pass a fake
# The picker only chooses keys from lists. Gemini's hidden "thinking" tokens count against max_tokens and are billed: a 6-day split spent
# about 3,860 of 3,984 output tokens thinking and the JSON was cut off, so the plan silently fell back to code (found by the plan eval,
# D-085). The evals use exactly these settings.
PICKER_CALL = {"node": "exercise_picker", "max_tokens": MAX_TOKENS, "temperature": 0.0, "json_mode": True, "thinking_budget": 0}


@dataclass(frozen=True)
class DayPicks:
    label: str
    keys: tuple[str, ...]
    source: Literal["model", "fallback", "none"]   # "none": too few allowed exercises fit this day to make a workout
    note: str | None = None


def _default_ask(user_id: UUID | None) -> Ask:
    def ask(prompt: str) -> LLMResult:
        return call_llm("mid", [("system", SYSTEM), ("human", prompt)], flow="plan_generation", user_id=user_id,
                        **PICKER_CALL)   # temperature 0: the same inputs give the same plan (D-052)
    return ask


def _day_limits(candidates: Sequence[ExerciseOption], wanted: int) -> tuple[int, int]:
    """The variety limits the validator will enforce for this day, from the SAME functions (so the prompt and the check cannot disagree)."""
    available = len({o.movement_pattern for o in candidates})
    return pattern_cap(wanted, available), min(wanted, available)


def pick_exercises(
    split: Split, allowed: Sequence[ExerciseOption], level: str, goal: str,
    *, per_day: int | None = None, focus: Sequence[str] = (), ask: Ask | None = None, user_id: UUID | None = None,
) -> list[DayPicks]:
    """One DayPicks per training day, in the split's order. `allowed` must already be filtered for this user.
    `per_day` is how many exercises a day should have (from the session length); default is by level.
    `focus` muscles add one exercise to the days that train them and steer the choice (D-060)."""
    ask = ask or _default_ask(user_id)
    cands = [day_candidates(d, allowed) for d in split.days]
    base = per_day if per_day is not None else EXERCISES_PER_DAY[level]
    wanted = [wanted_count(level, c, day_wanted(base, d, focus)) for c, d in zip(cands, split.days, strict=True)]
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
        requests = [DayRequest(i + 1, split.days[i].label, wanted[i], cands[i], problems.get(i, ()), *_day_limits(cands[i], wanted[i]))
                    for i in pending]
        try:
            answer = parse_answer(ask(build_user_prompt(level, goal, requests, focus)).text)
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
        keys = fallback_picks(cands[i], wanted[i], used, focus)
        used.extend(keys)
        results[i] = DayPicks(split.days[i].label, tuple(keys), "fallback", "; ".join(problems.get(i, ["model unavailable"])))
    return [results[i] for i in range(len(split.days))]
