"""Step 7.7e: the meal plan eval HARNESS with fakes (free). Real run: `python -m evals.run_llm meal`."""

import pytest

from app.calc.meal_pool import PoolFood
from app.calc.meal_solver import DayTargets
from app.llm.client import LLMResult
from app.workflows import pick_meals
from app.workflows.pick_meals import MEAL_CALL, MealPlanFailed, PoolTooSmall
from evals import cache as cache_mod
from evals import meal_eval
from evals.meal_cases import SCENARIOS, MealScenario


@pytest.fixture(autouse=True)
def private_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "DIR", tmp_path / "cache")


def food(key, name, diet_class, kcal=100.0, protein=10.0, syn=()):
    return PoolFood(1, key, name, "dish", diet_class, kcal, protein, 10.0, 2.0, "ready", tuple(syn), ())


FOODS = {f.key: f for f in [food("dal", "Dal", "vegan"), food("paneer", "Paneer", "vegetarian", syn=("cottage cheese",)),
                            food("egg", "Egg", "eggetarian"), food("chicken", "Chicken curry", "non_vegetarian", 200, 25)]}
T = DayTargets(kcal=1000, protein_g=60, carbs_g=100, fat_g=30, kcal_min=960, kcal_max=1040, protein_max_g=70)


def payload(*items_per_day):
    return {"days": [{"day_of_week": i + 1, "items": [{"food_key": k, "grams": g} for k, g in items]} for i, items in enumerate(items_per_day)]}


# ---------- the independent safety check ----------

def test_protein_above_the_cap_is_found():
    day = [("dal", 500), ("paneer", 500)]                       # 1,000 kcal (inside the band) but 100 g protein (the cap is 70 g)
    found = meal_eval.independent_safety(payload(day), FOODS, "vegetarian", (), T)
    assert found == ["day 1: protein 100 g is above the cap 70 g"]


def test_calories_inside_the_band_and_protein_under_the_cap_pass():
    foods = {**FOODS, "dal": food("dal", "Dal", "vegan", kcal=100, protein=6)}
    assert meal_eval.independent_safety(payload([("dal", 1000)]), foods, "vegan", (), T) == []      # 1,000 kcal, 60 g protein


def test_a_day_outside_the_calorie_band_is_found():
    found = meal_eval.independent_safety(payload([("dal", 700)]), FOODS, "vegan", (), T)
    assert any("700 kcal is outside 960 to 1040" in f for f in found)


def test_a_food_that_does_not_suit_the_diet_is_found():
    found = meal_eval.independent_safety(payload([("chicken", 100)]), FOODS, "vegetarian", (), T)
    assert any("Chicken curry (non_vegetarian) is not allowed for vegetarian" in f for f in found)


@pytest.mark.parametrize("diet, ok_keys", [("vegan", {"dal"}), ("vegetarian", {"dal", "paneer"}), ("eggetarian", {"dal", "paneer", "egg"}),
                                           ("non_vegetarian", {"dal", "paneer", "egg", "chicken"})])
def test_each_diet_allows_exactly_its_classes(diet, ok_keys):
    for key in FOODS:
        found = [f for f in meal_eval.independent_safety(payload([(key, 1)]), FOODS, diet, (), T) if "not allowed" in f]
        assert (not found) == (key in ok_keys), (diet, key)


def test_a_disliked_food_is_found_by_name_key_or_local_name():
    assert any("matches the dislike" in f for f in meal_eval.independent_safety(payload([("paneer", 1)]), FOODS, "vegetarian", ("PANEER",), T))
    assert any("matches the dislike" in f for f in meal_eval.independent_safety(payload([("paneer", 1)]), FOODS, "vegetarian", ("cottage",), T))
    assert not [f for f in meal_eval.independent_safety(payload([("dal", 1)]), FOODS, "vegetarian", ("paneer", "  "), T) if "dislike" in f]


def test_the_arithmetic_is_redone_from_the_foods_table_not_taken_from_the_payload():
    p = payload([("dal", 700)])
    p["days"][0]["items"][0]["kcal"] = 1000            # a payload that LIES about its calories
    assert any("700 kcal" in f for f in meal_eval.independent_safety(p, FOODS, "vegan", (), T))


# ---------- the model path: same settings as the app, cache, budget ----------

def llm(text='{"days": []}'):
    return LLMResult(text, "fake", 100, 20, 0, 0.001, 4)


def test_the_app_and_the_eval_share_one_set_of_call_settings_with_thinking_off():
    assert MEAL_CALL["thinking_budget"] == 0 and MEAL_CALL["temperature"] == 0.0 and MEAL_CALL["json_mode"] is True
    assert MEAL_CALL["node"] == "meal_picker" and MEAL_CALL["max_tokens"] == pick_meals.MAX_TOKENS


def test_the_apps_default_ask_sends_those_settings(monkeypatch):
    seen = {}
    monkeypatch.setattr(pick_meals, "call_llm", lambda tier, messages, **kw: seen.update(tier=tier, **kw) or "r")
    assert pick_meals._default_ask(None)("p") == "r"
    assert seen["tier"] == "mid" and seen["thinking_budget"] == 0 and seen["flow"] == "plan_generation" and seen["node"] == "meal_picker"


def test_the_eval_sends_them_too_and_logs_as_eval(monkeypatch):
    seen = []
    monkeypatch.setattr(meal_eval, "call_llm", lambda tier, messages, **kw: seen.append((tier, kw)) or llm())
    ask = meal_eval._cached_ask(cache_mod.Cache("meal"), {"real": 0, "max": 5})
    ask("a prompt")
    assert seen[0][0] == "mid" and seen[0][1]["flow"] == "eval" and seen[0][1]["thinking_budget"] == 0 and seen[0][1]["node"] == "meal_picker"


def test_the_cache_serves_the_same_prompt_and_a_settings_change_calls_again(monkeypatch):
    calls = []
    monkeypatch.setattr(meal_eval, "call_llm", lambda tier, messages, **kw: calls.append(1) or llm())
    cache = cache_mod.Cache("meal")
    counter = {"real": 0, "max": 5}
    ask = meal_eval._cached_ask(cache, counter)
    ask("p")
    ask("p")
    assert len(calls) == 1
    monkeypatch.setattr(meal_eval, "MEAL_CALL", {**MEAL_CALL, "thinking_budget": None})
    ask("p")
    assert len(calls) == 2


def test_a_budget_hit_raises_even_though_the_picker_swallows_model_errors(monkeypatch):
    """The real picker catches EVERY error from the model and falls back to code. The eval must not report those results as model results."""
    monkeypatch.setattr(meal_eval, "call_llm", lambda *a, **k: llm())

    def swallowing_picker(foods, diet, dislikes, targets, goal, emphasis, *, ask, cuisines=None):
        try:
            ask("one")
            ask("two")                                   # over the budget of 1
        except Exception:                                # noqa: BLE001 - exactly what pick_meals does
            pass
        raise MealPlanFailed("fell back")
    monkeypatch.setattr(meal_eval, "pick_meals", swallowing_picker)
    with pytest.raises(RuntimeError, match="budget"):
        meal_eval.run_meal_eval([], scenarios=SCENARIOS[:1], max_calls=1)


def test_a_pool_too_small_is_a_refusal_not_a_failure(monkeypatch):
    def refuse(*a, **k):
        raise PoolTooSmall("Your diet and dislikes leave no choice for: breakfast.")
    monkeypatch.setattr(meal_eval, "pick_meals", refuse)
    r = meal_eval.run_meal_eval([], scenarios=SCENARIOS[:1], call_ask=lambda cache, counter: None)[0]
    assert r.refused and "no choice for: breakfast" in r.refusal
    s = meal_eval.summarize([r])
    assert s["refused"] == 1 and s["scenario_pass_rate"] == 1.0 and s["safety_violation_rate"] == 0.0     # nothing made, nothing failed


# ---------- summary and scenarios ----------

def result(**over):
    base = dict(name="x", refused=False, refusal="", safety=(), problems=(), sources=("model", "fallback"), statuses=("ok", "issues"), repair_asked=False,
                model_calls=1, protein_pct=(100.0, 60.0), repeat_rate=0.2, tokens_in=1000, tokens_out=2000, cost_usd=0.01, latency_ms=10_000)
    return meal_eval.MealResult(**{**base, **over})


def test_a_safety_violation_or_a_verify_problem_fails_the_plan():
    assert result().passed
    assert not result(safety=("day 1: Chicken is not allowed for vegan",)).passed
    assert not result(problems=("day 2: no meals",)).passed


def test_the_summary_reports_quality_and_cost():
    s = meal_eval.summarize([result(), result(sources=("fallback", "fallback"), statuses=("issues", "issues"), repair_asked=True, protein_pct=(50.0, 50.0), cost_usd=0.03)])
    assert s["model_day_rate"] == 0.25 and s["ok_day_rate"] == 0.25 and s["repair_rate"] == 0.5
    assert s["mean_protein_ratio"] == pytest.approx(0.65) and s["min_protein_ratio"] == 0.5 and s["avg_cost_usd"] == pytest.approx(0.02)
    assert s["safety_violation_rate"] == 0.0 and s["scenario_pass_rate"] == 1.0


def test_the_scenario_set_covers_every_diet_and_the_hard_cases():
    assert {s.diet for s in SCENARIOS} == {"vegan", "vegetarian", "eggetarian", "non_vegetarian"}
    assert any("kidney" in s.profile.screening_flags for s in SCENARIOS) and any(len(s.dislikes) >= 3 for s in SCENARIOS)
    assert any(s.profile.goal == "muscle_gain" for s in SCENARIOS) and len({s.name for s in SCENARIOS}) == len(SCENARIOS)
    assert all(isinstance(s, MealScenario) for s in SCENARIOS)
