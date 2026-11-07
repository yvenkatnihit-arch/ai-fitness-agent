"""The 7-day meal workflow with a fake model: good answers, repair, fallback, outages and refusals."""

import copy
import json

import pytest

from app.calc.meal_pool import ALL_SLOTS, SLOTS
from app.calc.meal_solver import DayTargets
from app.llm.client import LLMBusy, LLMResult
from app.llm.meal_prompt import parse_answer
from app.workflows.pick_meals import MealPlanFailed, PoolTooSmall, pick_meals
from tests.meal_fixtures import make_foods

FOODS = make_foods()


def targets(kcal=1800, protein=80):
    return DayTargets(kcal, protein, kcal * 0.5 / 4, kcal * 0.28 / 9, kcal * 0.96, kcal * 1.04, protein * 1.15)


def down(prompt):
    raise LLMBusy()


def reply(days):
    return LLMResult(json.dumps({"days": [{"day": n, "meals": meals} for n, meals in days.items()]}), "m", 10, 10, 0, 0.0, 5)


class Script:
    """Fake `ask`: plays back scripted replies (or raises them) and remembers the prompts."""

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def run(ask, t=None, diet="vegetarian", dislikes=(), emphasis=None):
    return pick_meals(FOODS, diet, list(dislikes), t or targets(), "muscle_gain", emphasis, ask=ask)


@pytest.fixture(scope="module")
def baseline():
    """A week made entirely by the code fallback: used as a source of picks a 'perfect model' could return."""
    return run(down)


def model_answer(baseline, only_ok=True):
    return {d.day: d.picks for d in baseline.days if d.solution.status == "ok" or not only_ok}


def ok_days(baseline):
    return [d.day for d in baseline.days if d.solution.status == "ok"]


def test_the_fallback_alone_makes_a_safe_week(baseline):
    assert len(baseline.days) == 7 and [d.day for d in baseline.days] == list(range(1, 8))
    assert all(d.source == "fallback" and d.solution.status != "infeasible" for d in baseline.days)
    assert baseline.model_called is False and baseline.slots == SLOTS and baseline.portion_scale == 1.0
    assert ok_days(baseline) == list(range(1, 8)), "with a modest protein target every fallback day is fully ok"


def test_a_good_model_answer_is_used_with_one_call(baseline):
    good = model_answer(baseline)
    assert sorted(good) == list(range(1, 8))
    ask = Script(reply(good))
    plan = run(ask)
    assert len(ask.prompts) == 1 and plan.repair_asked is False and plan.model_called is True
    assert all(d.source == "model" and d.picks == good[d.day] and d.solution.status == "ok" for d in plan.days)


def test_the_prompt_has_keys_names_and_tags_but_no_raw_numbers(baseline):
    ask = Script(reply(model_answer(baseline)))
    run(ask)
    prompt = ask.prompts[0]
    assert "- paneer | Paneer | protein-rich, calorie-dense" in prompt and "- dal_0 | Dal 0" in prompt
    assert "- chaas | Chaas | protein-rich, light" in prompt and "egg" not in prompt          # a vegetarian is never offered egg
    assert "kcal" not in prompt and "protein_g" not in prompt
    assert "Plan these days: 1, 2, 3, 4, 5, 6, 7" in prompt and "Diet: vegetarian. Goal: muscle gain." in prompt
    assert "Priority" not in prompt and "lot of protein" not in prompt                      # no emphasis by default


def test_emphasis_reaches_the_prompt():
    ask = Script(LLMBusy())
    run(ask, emphasis="low_protein")
    assert "must limit protein" in ask.prompts[0]
    ask = Script(LLMBusy())
    run(ask, emphasis="high_protein")
    assert "lot of protein" in ask.prompts[0]


def test_a_made_up_dish_is_rejected_and_only_that_day_is_asked_again(baseline):
    good = copy.deepcopy(model_answer(baseline))
    day = ok_days(baseline)[0]
    bad = copy.deepcopy(good)
    bad[day]["lunch"]["protein"] = "secret_curry"
    ask = Script(reply(bad), reply({day: good[day]}))
    plan = run(ask)
    assert f"Plan these days: {day}" in ask.prompts[1] and "'secret_curry' is not in the allowed list" in ask.prompts[1]
    assert next(d for d in plan.days if d.day == day).picks == good[day] and plan.repair_asked


def test_the_same_dal_twice_in_a_day_is_rejected(baseline):
    day = ok_days(baseline)[0]
    bad = copy.deepcopy(model_answer(baseline))
    bad[day]["dinner"]["protein"] = bad[day]["lunch"]["protein"]
    ask = Script(reply(bad), LLMBusy())
    run(ask)
    assert "is used more than once in the day" in ask.prompts[1]


def test_using_one_dish_all_week_is_rejected_by_the_repeat_cap(baseline):
    lazy = {}
    for n in range(1, 8):
        meals = copy.deepcopy(baseline.days[n - 1].picks)
        meals["breakfast"]["main"] = "brk_0"
        lazy[n] = meals
    ask = Script(reply(lazy), LLMBusy())
    run(ask)
    assert "used too often this week" in ask.prompts[1]


def test_two_bad_answers_fall_back_to_code_picks(baseline):
    junk = reply({n: {"breakfast": {"main": "nope"}} for n in range(1, 8)})
    ask = Script(junk, junk)
    plan = run(ask)
    assert len(ask.prompts) == 2 and all(d.source == "fallback" for d in plan.days)
    assert all(d.solution.status != "infeasible" for d in plan.days)


def test_garbage_text_means_fallback_for_every_day():
    ask = Script(LLMResult("sorry, I can't", "m", 1, 1, 0, 0, 1), LLMResult("{}", "m", 1, 1, 0, 0, 1))
    plan = run(ask)
    assert all(d.source == "fallback" for d in plan.days) and plan.model_called is True


def test_an_outage_still_gives_a_complete_week():
    ask = Script(LLMBusy())
    plan = run(ask)
    assert len(ask.prompts) == 1                                               # asked once, did not retry a dead model
    assert len(plan.days) == 7 and plan.model_called is False and all(d.source == "fallback" for d in plan.days)


def test_a_missing_day_is_asked_again(baseline):
    partial = {n: p for n, p in model_answer(baseline).items() if n != 7}
    ask = Script(reply(partial), LLMBusy())
    run(ask)
    assert "day 7" in ask.prompts[1] and "missing from your answer" in ask.prompts[1]


def test_a_day_with_issues_is_repaired_with_the_solvers_own_words():
    """The model's first answer is valid but the solver finds protein too low: the second prompt quotes the solver."""
    low_protein = {}
    for n in range(1, 8):
        low_protein[n] = {"breakfast": {"main": "brk_0", "extra": "fruit_0"},
                          "lunch": {"staple": "rice_0", "protein": f"dal_{n % 8}", "vegetable": f"sabzi_{n % 8}", "side": None},
                          "evening_snack": {"snack": "fruit_1"},
                          "dinner": {"staple": "rice_1", "protein": f"dal_{(n + 3) % 8}", "vegetable": f"sabzi_{(n + 4) % 8}", "side": None}}
    ask = Script(reply(low_protein), LLMBusy())
    plan = run(ask, t=targets(1800, 140))                  # a high protein target the plain dal days cannot meet
    assert len(ask.prompts) == 2 and "rejected" in ask.prompts[1]
    assert any(word in ask.prompts[1] for word in ("protein", "carbs", "fat", "kcal", "has"))
    assert all(d.solution.status != "infeasible" for d in plan.days)


def test_a_big_day_gets_a_mid_morning_meal_and_bigger_portions():
    plan = run(Script(LLMBusy()), t=targets(3000, 150))
    assert plan.slots == ALL_SLOTS and plan.portion_scale == 1.36
    assert all("mid_morning" in d.picks and d.solution.status != "infeasible" for d in plan.days)
    assert all(2865 <= d.solution.totals.kcal <= 3135 for d in plan.days)


def test_every_day_respects_the_hard_limits(baseline):
    t = targets()
    for d in baseline.days:
        assert t.kcal_min - 1.5 <= d.solution.totals.kcal <= t.kcal_max + 1.5
        assert d.solution.totals.protein_g <= t.protein_max_g + 1.5


def test_the_week_varies_even_from_the_fallback(baseline):
    assert len({d.picks["lunch"]["protein"] for d in baseline.days}) >= 4
    assert len({d.picks["breakfast"]["main"] for d in baseline.days}) >= 4


def test_it_is_deterministic(baseline):
    again = run(down)
    assert [d.picks for d in again.days] == [d.picks for d in baseline.days]


def test_dislikes_are_respected_in_every_day():
    plan = run(down, dislikes=["dal 3", "sabzi 5"])
    keys = {k for d in plan.days for meal in d.picks.values() for k in meal.values() if k}
    assert "dal_3" not in keys and "sabzi_5" not in keys


def test_a_diet_with_no_option_for_a_required_meal_is_refused():
    only_rice = [f for f in FOODS if f.category == "dish_rice"]
    with pytest.raises(PoolTooSmall) as e:
        pick_meals(only_rice, "vegan", [], targets(), "muscle_gain", ask=down)
    assert "no choice for" in str(e.value) and "lunch" in str(e.value)


def test_an_impossible_target_is_refused_with_a_clear_message():
    with pytest.raises(MealPlanFailed) as e:
        run(down, t=targets(9000, 300))
    assert "day 1" in str(e.value) and "dislike" in str(e.value)


def test_parse_answer():
    assert parse_answer('{"days": [{"day": 2, "meals": {"lunch": {}}}]}') == {2: {"lunch": {}}}
    assert parse_answer('```json\n{"days": [{"day": 1, "meals": {}}]}\n```') == {1: {}}
    for junk in ("not json", "[1]", '{"days": "x"}', '{"days": [{"day": "1", "meals": {}}]}', '{"days": [{"day": 1}]}'):
        assert parse_answer(junk) == {}
