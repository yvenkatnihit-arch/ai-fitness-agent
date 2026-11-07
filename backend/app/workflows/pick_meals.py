"""Build a 7-day meal plan (Step 6.7c, D-066): the model chooses dishes, code validates, the solver sets portions.

Per day: model picks -> structural checks (app.calc.meal_week) -> portions by the solver (app.calc.meal_solver) ->
if the solver reports issues, that day is re-asked ONCE with the solver's own words -> if it still does not work, code
picks (a rotation search scored by the solver). So a plan is always made of valid, safe days, or we say we cannot.
Nothing here saves anything: saving as a pending proposal is step 6.7d.
"""

import logging
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.calc.meal_pool import PoolFood, SlotPool, build_pool, shares_for, slots_for
from app.calc.meal_portions import portion_scale_for
from app.calc.meal_solver import DaySolution, DayTargets, solve_day
from app.calc.meal_week import DayPicks, fallback_day, to_items, validate_week, week_usage
from app.llm.client import LLMResult, call_llm
from app.llm.meal_prompt import SYSTEM, build_user_prompt, parse_answer

logger = logging.getLogger(__name__)

DAYS = 7
MAX_TOKENS = 8000          # generous: Gemini's own reasoning tokens count toward this limit
FALLBACK_TRIES = 12        # rotations the code search tries per day
Ask = Callable[[str], LLMResult]


class PoolTooSmall(Exception):
    """The user's diet and dislikes leave a meal without a required dish. str(e) is safe to show."""


class MealPlanFailed(Exception):
    """No safe day could be built for some day. str(e) is safe to show."""


@dataclass(frozen=True)
class DayPlan:
    day: int                                  # 1 to 7
    picks: DayPicks
    solution: DaySolution
    source: Literal["model", "fallback"]


@dataclass(frozen=True)
class WeekPlan:
    days: tuple[DayPlan, ...]
    slots: tuple[str, ...]
    emphasis: str | None
    portion_scale: float
    thin_roles: dict[str, tuple[str, ...]]    # meals whose choice is thin (the plan will repeat dishes)
    model_called: bool
    repair_asked: bool


def _default_ask(user_id: UUID | None) -> Ask:
    def ask(prompt: str) -> LLMResult:
        return call_llm("mid", [("system", SYSTEM), ("human", prompt)], flow="plan_generation", node="meal_picker",
                        max_tokens=MAX_TOKENS, user_id=user_id, temperature=0.0, json_mode=True)
    return ask


def _score(solution: DaySolution) -> tuple[int, float, int]:
    """Lower is better: ok first, then MORE protein (up to the target; the goal-critical number), then fewer issues.
    Infeasible is always worst."""
    protein = min(solution.percent_of_target.get("protein", 0.0), 100.0)
    return ({"ok": 0, "issues": 1, "infeasible": 2}[solution.status], -protein, len(solution.issues))


def _best_fallback(pool: dict[str, SlotPool], slots: Sequence[str], index: int, targets: DayTargets, shares, scale: float,
                   emphasis: str | None, usage) -> tuple[DayPicks, DaySolution]:
    best: tuple[DayPicks, DaySolution] | None = None
    for offset in range(FALLBACK_TRIES):
        picks = fallback_day(pool, slots, index, offset, emphasis, usage)
        solution = solve_day(to_items(picks, pool, slots), targets, shares, scale)
        if best is None or _score(solution) < _score(best[1]):
            best = (picks, solution)
        if solution.status == "ok":
            break
    if best is None:
        raise RuntimeError("FALLBACK_TRIES must be at least 1")
    return best


def pick_meals(foods: Sequence[PoolFood], diet_type: str, dislikes: Collection[str], targets: DayTargets, goal: str,
               emphasis: str | None = None, *, ask: Ask | None = None, user_id: UUID | None = None) -> WeekPlan:
    slots = slots_for(targets.kcal)
    shares = shares_for(slots)
    scale = portion_scale_for(targets.kcal)
    pool = build_pool(foods, diet_type, dislikes, slots)
    empty = [s.replace("_", " ") for s in slots if pool[s].missing]
    if empty:
        raise PoolTooSmall(f"Your diet and dislikes leave no choice for: {', '.join(empty)}. Try removing a dislike.")
    ask = ask or _default_ask(user_id)

    accepted: dict[int, tuple[DayPicks, DaySolution]] = {}      # days the model got fully right
    candidates: dict[int, tuple[DayPicks, DaySolution]] = {}    # the model's best try for days with issues
    known: dict[int, DayPicks] = {}                              # every structurally valid day the model has answered
    pending = list(range(DAYS))
    feedback: dict[int, list[str]] = {}
    model_called = repair_asked = False

    for attempt in range(2):
        if not pending:
            break
        prompt = build_user_prompt(diet_type, goal, emphasis, slots, pool, [i + 1 for i in pending],
                                   {i + 1: p for i, p in feedback.items()})
        try:
            answer = parse_answer(ask(prompt).text)
        except Exception:  # noqa: BLE001 - LLMBusy / LLMFailed: the week is still made, by the fallback
            logger.warning("meal picker call failed; using code picks for %d day(s)", len(pending))
            break
        model_called = True
        repair_asked = repair_asked or attempt == 1
        trial: list[object] = [known.get(i) for i in range(DAYS)]
        for i in pending:
            if answer.get(i + 1) is not None:
                trial[i] = answer[i + 1]
        problems = validate_week(trial, pool, slots)
        next_pending: list[int] = []
        feedback = {}
        for i in pending:
            if answer.get(i + 1) is None:
                feedback[i] = ["this day was missing from your answer"]
                next_pending.append(i)
            elif i in problems:
                feedback[i] = problems[i]
                next_pending.append(i)
            else:
                picks = trial[i]
                known[i] = picks  # type: ignore[assignment]
                solution = solve_day(to_items(picks, pool, slots), targets, shares, scale)  # type: ignore[arg-type]
                if solution.status == "ok":
                    accepted[i] = (picks, solution)  # type: ignore[assignment]
                else:
                    candidates[i] = (picks, solution)  # type: ignore[assignment]
                    feedback[i] = list(solution.issues)
                    next_pending.append(i)
        pending = next_pending

    usage = week_usage([picks for picks, _ in accepted.values()])    # dishes the model already used on its good days
    plans: list[DayPlan] = []
    for i in range(DAYS):
        if i in accepted:
            picks, solution = accepted[i]
            plans.append(DayPlan(i + 1, picks, solution, "model"))
            continue
        fb_picks, fb_solution = _best_fallback(pool, slots, i, targets, shares, scale, emphasis, usage)
        if i in candidates and _score(candidates[i][1]) <= _score(fb_solution):
            picks, solution = candidates[i]
            plans.append(DayPlan(i + 1, picks, solution, "model"))
        else:
            plans.append(DayPlan(i + 1, fb_picks, fb_solution, "fallback"))
        usage.update(week_usage([plans[-1].picks]))
        if plans[-1].solution.status == "infeasible":
            raise MealPlanFailed(f"We could not build a safe meal day {i + 1} from the foods available to you. "
                                 "Try removing a dislike or changing your diet type.")
    thin = {s: pool[s].thin for s in slots if pool[s].thin}
    return WeekPlan(tuple(plans), tuple(slots), emphasis, scale, thin, model_called, repair_asked)
