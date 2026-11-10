"""Evaluate 7-day meal plan generation with the real dish picker (Step 7.7e, D-086).

Same steps as the app (pool, model picks the week, code validates, solver sets portions, repair round, code fallback, build and verify
the payload), with no database writes. The plan is then re-checked INDEPENDENTLY from the foods table, with arithmetic written here:

  safety (must be 0):  a food that does not suit the diet, a disliked food, a day outside the calorie band, protein above its cap,
                       a verify_payload problem
  how well it did:     days chosen by the model (vs the code fallback), repair rounds, solver status, protein reached against the
                       target, dishes repeated across the week, tokens, cost and latency (the real cost of a plan)
"""

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from app.calc.engine import calculate_targets
from app.calc.meal_plan_payload import build_payload, verify_payload
from app.calc.meal_pool import PoolFood
from app.calc.meal_solver import DayTargets, day_targets
from app.calc.meal_week import emphasis_for
from app.llm.client import LLMResult, call_llm, model_name
from app.llm.meal_prompt import SYSTEM
from app.workflows.pick_meals import MEAL_CALL, MealPlanFailed, PoolTooSmall, pick_meals
from evals import cache as cache_mod
from evals.meal_cases import SCENARIOS, MealScenario

MAX_CALLS = 20
# Written here on purpose (not imported from the app): which diet classes each diet may eat.
DIET_OK = {"vegan": {"vegan"}, "vegetarian": {"vegan", "vegetarian"}, "eggetarian": {"vegan", "vegetarian", "eggetarian"},
           "non_vegetarian": {"vegan", "vegetarian", "eggetarian", "non_vegetarian"}}


@dataclass(frozen=True)
class MealResult:
    name: str
    refused: bool
    refusal: str
    safety: tuple[str, ...]
    problems: tuple[str, ...]          # verify_payload problems
    sources: tuple[str, ...]           # per day: model | fallback
    statuses: tuple[str, ...]          # per day: ok | issues
    repair_asked: bool
    model_calls: int
    protein_pct: tuple[float, ...]     # per day: protein as a percent of the target
    repeat_rate: float                 # share of dish slots in the week that repeat a dish already used that week
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int

    @property
    def passed(self) -> bool:
        return not self.safety and not self.problems


def independent_safety(payload: dict, foods: dict[str, PoolFood], diet: str, dislikes: Sequence[str], t: DayTargets,
                       cuisines: Sequence[str] | None = None) -> list[str]:
    out = []
    wanted = [d.casefold().strip() for d in dislikes if d.strip()]
    for day in payload["days"]:
        kcal = protein = 0.0
        for item in day["items"]:
            f = foods[item["food_key"]]
            if f.diet_class not in DIET_OK[diet]:
                out.append(f"day {day['day_of_week']}: {f.name} ({f.diet_class}) is not allowed for {diet}")
            if cuisines is not None and not set(cuisines) & set(f.cuisines):
                out.append(f"day {day['day_of_week']}: {f.name} is not from the cuisines {list(cuisines)}")
            names = [f.name.casefold(), f.key.casefold(), *(s.casefold() for s in f.synonyms)]
            hit = [w for w in wanted if any(w in n for n in names)]
            if hit:
                out.append(f"day {day['day_of_week']}: {f.name} matches the dislike {hit}")
            kcal += item["grams"] * f.kcal / 100          # arithmetic redone here from the foods table
            protein += item["grams"] * f.protein_g / 100
        if not t.kcal_min - 1.5 <= kcal <= t.kcal_max + 1.5:      # 1.5 kcal: the portions are rounded to household steps
            out.append(f"day {day['day_of_week']}: {kcal:.0f} kcal is outside {t.kcal_min:.0f} to {t.kcal_max:.0f}")
        if protein > t.protein_max_g + 1.0:
            out.append(f"day {day['day_of_week']}: protein {protein:.0f} g is above the cap {t.protein_max_g:.0f} g")
    return out


def _cached_ask(cache, counter: dict) -> Callable[[str], LLMResult]:
    def ask(prompt: str) -> LLMResult:
        k = cache_mod.key(model_name("mid"), SYSTEM, repr(sorted(MEAL_CALL.items())), prompt)
        hit = cache.get(k)
        if hit is None:
            if counter["real"] >= counter["max"]:
                counter["over"] = True   # the picker catches ANY model error and falls back, so remember it and raise afterwards
                raise RuntimeError(f"eval budget reached: {counter['max']} real calls in one run")
            r = call_llm("mid", [("system", SYSTEM), ("human", prompt)], flow="eval", user_id=None, **MEAL_CALL)
            counter["real"] += 1
            hit = {"text": r.text, "in": r.input_tokens, "out": r.output_tokens, "cost": r.cost_usd, "ms": r.latency_ms}
            cache.put(k, hit)
        return LLMResult(hit["text"], model_name("mid"), hit["in"], hit["out"], 0, hit["cost"], hit["ms"])
    return ask


def _run(sc: MealScenario, foods: list[PoolFood], ask) -> MealResult:
    engine = calculate_targets(sc.profile)
    t = day_targets(engine, weight_kg=sc.profile.weight_kg, sex=sc.profile.sex, flags=sc.profile.screening_flags)
    emphasis = emphasis_for(engine.protein_g, engine.calorie_target_kcal, sc.profile.screening_flags)
    empty = dict(safety=(), problems=(), sources=(), statuses=(), repair_asked=False, model_calls=0, protein_pct=(), repeat_rate=0.0,
                 tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=0)
    try:
        week = pick_meals(foods, sc.diet, list(sc.dislikes), t, sc.profile.goal, emphasis, ask=ask, cuisines=sc.cuisines)
    except (PoolTooSmall, MealPlanFailed) as e:
        return MealResult(sc.name, True, str(e), **empty)
    payload = build_payload(week, t, diet_type=sc.diet, goal=sc.profile.goal, week_start=date(2026, 11, 9), numbers_hidden=False)
    by_key = {f.key: f for f in foods}
    problems = verify_payload(payload, by_key, diet_type=sc.diet, dislikes=sc.dislikes, targets=t, cuisines=sc.cuisines)
    keys = [i["food_key"] for d in payload["days"] for i in d["items"]]
    u = week.usage
    return MealResult(
        sc.name, False, "", tuple(independent_safety(payload, by_key, sc.diet, sc.dislikes, t, sc.cuisines)), tuple(problems),
        tuple(d["source"] for d in payload["days"]), tuple(d["status"] for d in payload["days"]), week.repair_asked, int(u["model_calls"]),
        tuple(d["percent_of_target"].get("protein", 0.0) for d in payload["days"]),
        (len(keys) - len(set(keys))) / len(keys) if keys else 0.0, int(u["input_tokens"]), int(u["output_tokens"]), float(u["cost_usd"]), int(u["latency_ms"]))


def run_meal_eval(foods: list[PoolFood], *, use_cache: bool = True, max_calls: int = MAX_CALLS, scenarios: list[MealScenario] | None = None,
                  call_ask: Callable | None = None) -> list[MealResult]:
    """`call_ask(cache, counter)` lets tests replace the real model."""
    cache = cache_mod.Cache("meal", use_cache)
    out, spent = [], 0
    for sc in scenarios if scenarios is not None else SCENARIOS:
        counter = {"real": spent, "max": max_calls}
        result = _run(sc, foods, (call_ask or _cached_ask)(cache, counter))
        if counter.get("over"):
            cache.save()
            raise RuntimeError(f"eval budget reached: {max_calls} real calls in one run")
        out.append(result)
        spent = counter["real"]
        cache.save()   # after EVERY scenario: a crash or a dropped connection must not lose paid results
    cache.save()
    return out


def summarize(results: list[MealResult]) -> dict:
    made = [r for r in results if not r.refused]
    n, m = len(results) or 1, len(made) or 1
    days = [s for r in made for s in r.sources]
    statuses = [s for r in made for s in r.statuses]
    protein = [p for r in made for p in r.protein_pct]
    return {
        "scenarios": len(results), "refused": sum(r.refused for r in results), "refused_rate": sum(r.refused for r in results) / n,
        "scenario_pass_rate": sum(r.passed for r in made) / len(made) if made else 1.0,
        "safety_violation_rate": sum(bool(r.safety) for r in made) / m, "payload_problem_rate": sum(bool(r.problems) for r in made) / m,
        "model_day_rate": days.count("model") / len(days) if days else 1.0,
        "repair_rate": sum(r.repair_asked for r in made) / m,
        "ok_day_rate": statuses.count("ok") / len(statuses) if statuses else 1.0,
        "mean_protein_ratio": statistics.mean(protein) / 100 if protein else 1.0,     # protein reached / target, per day
        "min_protein_ratio": min(protein) / 100 if protein else 1.0,
        "mean_repeat_rate": statistics.mean(r.repeat_rate for r in made) if made else 0.0,
        "avg_tokens_out": statistics.mean(r.tokens_out for r in made) if made else 0,
        "avg_cost_usd": statistics.mean(r.cost_usd for r in made) if made else 0.0,
        "total_cost_usd": sum(r.cost_usd for r in results),
        "median_latency_ms": statistics.median(r.latency_ms for r in made) if made else 0,
    }
