"""Evaluate workout plan generation with the real exercise picker (Step 7.7d, D-085).

For each made-up user it runs the SAME steps as the app (filter the library, model picks, code validates and falls back, build the
plan, validate the plan), without the database or saving anything. Then it checks the plan independently, from the raw exercise
fields (not by reusing the filter, so a bug in the filter cannot hide itself):

  safety (must be 0):   an exercise that hits a reported injury, is above the user's level, is for the wrong place, needs equipment
                        the user lacks, or is blocked
  plan checks (0):      validate_payload problems, a muscle above the weekly set cap
  how well the model did: share of days the MODEL chose (not the code fallback), retries, pattern coverage of each day, exercises per
                        day versus the session target, focus muscles honoured, exercises repeated across days
"""

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from app.calc.exercise_filter import LEVEL_ORDER, ExerciseNeeds, ExerciseOption, filter_exercises, setting_for
from app.calc.session_time import exercises_for_session
from app.calc.splits import split_by_key
from app.calc.workout_edit import weekly_sets
from app.calc.workout_plan import DayPick, build_payload, validate_payload
from app.llm.client import LLMResult, call_llm, model_name
from app.llm.picker_prompt import SYSTEM
from app.safety.safety_config import MAX_WEEKLY_SETS_PER_MUSCLE
from app.workflows.pick_exercises import PICKER_CALL, pick_exercises
from evals import cache as cache_mod
from evals.workout_cases import SCENARIOS, Scenario

MAX_CALLS = 40


@dataclass(frozen=True)
class WorkoutResult:
    name: str
    refused: bool                      # the app would say "not enough safe exercises" (an acceptable outcome, never a failure by itself)
    refusal: str
    safety: tuple[str, ...]            # each safety violation, in words
    problems: tuple[str, ...]          # validate_payload problems
    cap_breaches: tuple[str, ...]      # muscles above the weekly cap
    sources: tuple[str, ...]           # per training day: model | fallback | none
    asks: int                          # model calls (more than 1 = a retry)
    pattern_coverage: float
    counts_ok: float                   # share of days within 1 exercise of the session target
    focus_ok: float | None             # share of focus muscles with at least 2 exercises (None when no focus)
    repeat_rate: float                 # share of exercise slots that repeat an exercise from another day
    tokens: int
    cost_usd: float
    latency_ms: int

    @property
    def passed(self) -> bool:
        return not self.safety and not self.problems and not self.cap_breaches


def safety_violations(keys: list[str], library: dict[str, ExerciseOption], sc: Scenario) -> list[str]:
    """Independent re-check from the raw fields. Written separately from app.calc.exercise_filter on purpose."""
    setting = "home" if sc.place == "home" else "gym"
    out = []
    for key in keys:
        o = library[key]
        hit = sorted(set(o.contraindications) & sc.injuries)
        if hit:
            out.append(f"{o.name}: hits injury {hit}")
        if LEVEL_ORDER[o.difficulty] > LEVEL_ORDER[sc.level]:
            out.append(f"{o.name}: {o.difficulty} is above {sc.level}")
        if o.location not in (setting, "both"):
            out.append(f"{o.name}: a {o.location} exercise in a {setting} plan")
        if setting == "home" and not set(o.equipment) <= sc.equipment:
            out.append(f"{o.name}: needs {sorted(set(o.equipment) - sc.equipment)}")
        if o.review_status == "blocked":
            out.append(f"{o.name}: blocked")
    return out


def _cached_ask(cache, counter: dict) -> Callable[[str], LLMResult]:
    def ask(prompt: str) -> LLMResult:
        k = cache_mod.key(model_name("mid"), SYSTEM, repr(sorted(PICKER_CALL.items())), prompt)
        hit = cache.get(k)
        if hit is None:
            if counter["real"] >= counter["max"]:
                counter["over"] = True   # the picker catches ANY error from the model and falls back to code, so remember it and raise afterwards
                raise RuntimeError(f"eval budget reached: {counter['max']} real calls in one run")
            r = call_llm("mid", [("system", SYSTEM), ("human", prompt)], flow="eval", user_id=None, **PICKER_CALL)
            counter["real"] += 1
            hit = {"text": r.text, "in": r.input_tokens, "out": r.output_tokens, "cost": r.cost_usd, "ms": r.latency_ms}
            cache.put(k, hit)
        counter["asks"] += 1
        counter["tokens"] += hit["in"] + hit["out"]
        counter["cost"] += hit["cost"]
        counter["ms"] += hit["ms"]
        return LLMResult(hit["text"], model_name("mid"), hit["in"], hit["out"], 0, hit["cost"], hit["ms"])
    return ask


def _run(sc: Scenario, library: list[ExerciseOption], ask, counter: dict) -> WorkoutResult:
    by_key = {o.key: o for o in library}
    split = split_by_key(sc.split_key)
    needs = ExerciseNeeds(setting_for(sc.place), sc.level, sc.injuries, sc.equipment)
    allowed = filter_exercises(library, needs)
    per_day = exercises_for_session(sc.level, sc.goal, sc.pace, sc.minutes)
    picks = pick_exercises(split, allowed, sc.level, sc.goal, per_day=per_day, focus=sc.focus, ask=ask)
    sources = tuple(p.source for p in picks)
    base = dict(name=sc.name, sources=sources, asks=counter["asks"], tokens=counter["tokens"], cost_usd=counter["cost"], latency_ms=counter["ms"])
    empty = [p.label for p in picks if p.source == "none"]
    if empty:
        return WorkoutResult(refused=True, refusal=f"not enough safe exercises for: {', '.join(empty)}", safety=(), problems=(), cap_breaches=(),
                             pattern_coverage=1.0, counts_ok=1.0, focus_ok=None, repeat_rate=0.0, **base)
    payload = build_payload(split, [DayPick(p.label, p.keys) for p in picks], by_key, level=sc.level, goal=sc.goal, pace=sc.pace, flagged=False,
                            week_start=date(2026, 11, 9), focus=sc.focus)
    problems = validate_payload(payload, set(by_key))
    all_keys = [k for p in picks for k in p.keys]
    caps = tuple(f"{m}: {n} sets" for m, n in sorted(weekly_sets(payload, by_key).items()) if n > MAX_WEEKLY_SETS_PER_MUSCLE)
    coverage = statistics.mean(len({by_key[k].movement_pattern for k in p.keys} & set(d.patterns)) / len(d.patterns) for p, d in zip(picks, split.days, strict=True))
    counts_ok = statistics.mean(abs(len(p.keys) - per_day) <= 1 for p in picks)
    main = [by_key[k].muscle_groups[0] for k in all_keys]
    focus_ok = (statistics.mean(main.count(m) >= 2 for m in sc.focus) if sc.focus else None)
    repeats = len(all_keys) - len(set(all_keys))
    return WorkoutResult(refused=False, refusal="", safety=tuple(safety_violations(all_keys, by_key, sc)), problems=tuple(problems), cap_breaches=caps,
                         pattern_coverage=coverage, counts_ok=counts_ok, focus_ok=focus_ok, repeat_rate=repeats / len(all_keys) if all_keys else 0.0, **base)


def run_workout_eval(library: list[ExerciseOption], *, use_cache: bool = True, max_calls: int = MAX_CALLS,
                     scenarios: list[Scenario] | None = None, call_ask: Callable | None = None) -> list[WorkoutResult]:
    """`call_ask(cache, counter)` lets tests replace the real model."""
    cache = cache_mod.Cache("workout", use_cache)
    out = []
    spent = {"real": 0}
    for sc in scenarios if scenarios is not None else SCENARIOS:
        counter = {"real": spent["real"], "max": max_calls, "asks": 0, "tokens": 0, "cost": 0.0, "ms": 0}
        ask = (call_ask or _cached_ask)(cache, counter)
        result = _run(sc, library, ask, counter)
        if counter.get("over"):   # never report fallback results as if the model had been asked
            cache.save()
            raise RuntimeError(f"eval budget reached: {max_calls} real calls in one run")
        out.append(result)
        spent["real"] = counter["real"]
    cache.save()
    return out


def summarize(results: list[WorkoutResult]) -> dict:
    n = len(results) or 1
    made = [r for r in results if not r.refused]
    days = [s for r in made for s in r.sources]
    m = len(made) or 1
    focus = [r.focus_ok for r in made if r.focus_ok is not None]
    return {
        "scenarios": len(results), "refused": sum(r.refused for r in results),
        "scenario_pass_rate": sum(r.passed for r in made) / len(made) if made else 1.0,   # nothing made, nothing failed
        "safety_violation_rate": sum(bool(r.safety) for r in made) / m,
        "payload_problem_rate": sum(bool(r.problems) for r in made) / m,
        "weekly_cap_breach_rate": sum(bool(r.cap_breaches) for r in made) / m,
        "refused_rate": sum(r.refused for r in results) / n,
        "model_day_rate": days.count("model") / len(days) if days else 1.0,
        "retry_rate": sum(r.asks > 1 for r in made) / m,
        "mean_pattern_coverage": statistics.mean(r.pattern_coverage for r in made) if made else 1.0,
        "count_ok_rate": statistics.mean(r.counts_ok for r in made) if made else 1.0,
        "focus_ok_rate": statistics.mean(focus) if focus else 1.0,
        "mean_repeat_rate": statistics.mean(r.repeat_rate for r in made) if made else 0.0,
        "avg_tokens": statistics.mean(r.tokens for r in results) if results else 0,
        "total_cost_usd": sum(r.cost_usd for r in results),
        "median_latency_ms": statistics.median(r.latency_ms for r in results) if results else 0,
    }
