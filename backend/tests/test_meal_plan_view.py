"""The meal plan screen's data: model usage accounting, the 'how made' summary, portion text, the active-plan view (pure Python)."""

import json
from datetime import date, datetime, timezone

import pytest

from app.calc.meal_plan_payload import CHECKS, CHECKS_HIDDEN, build_payload, hide_numbers, portion_text
from app.calc.meal_solver import DayTargets
from app.llm.client import LLMBusy, LLMResult
from app.schemas.meal_plans import to_active_meal_plan
from app.workflows.pick_meals import pick_meals
from tests.meal_fixtures import make_foods

FOODS = make_foods()
TARGETS = DayTargets(1800, 80, 225, 56, 1728, 1872, 92)
MONDAY = date(2026, 11, 9)


def down(prompt):
    raise LLMBusy()


@pytest.fixture(scope="module")
def code_week():
    return pick_meals(FOODS, "vegetarian", [], TARGETS, "muscle_gain", "high_protein", ask=down)


@pytest.mark.parametrize("grams,unit,qty,text", [
    (225.0, "katori", 1.5, "1.5 katori (225 g)"), (86.0, "piece", 2.0, "2 pieces (86 g)"), (43.0, "piece", 1.0, "1 piece (43 g)"),
    (150.0, None, None, "150 g"), (258.9, "glass", 1.0, "1 glass (258.9 g)"),
])
def test_portion_text(grams, unit, qty, text):
    assert portion_text(grams, unit, qty) == text


def test_usage_sums_every_model_call():
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return LLMResult("{}", "m", input_tokens=2000, output_tokens=5000, cached_tokens=0, cost_usd=0.0131, latency_ms=21000)

    week = pick_meals(FOODS, "vegetarian", [], TARGETS, "muscle_gain", None, ask=ask)    # empty answers: asks twice, then code picks
    assert len(calls) == 2 and week.model_called
    assert week.usage == {"model_calls": 2, "input_tokens": 4000, "output_tokens": 10000, "cost_usd": 0.0262, "latency_ms": 42000}


def test_without_the_model_usage_is_zero_and_the_panel_says_no_generation(code_week):
    assert code_week.usage["model_calls"] == 0
    made = build_payload(code_week, TARGETS, diet_type="vegetarian", goal="muscle_gain", week_start=MONDAY, numbers_hidden=False)["how_made"]
    assert made["generation"] is None and made["days_from_model"] == 0 and made["days_from_code"] == 7
    assert made["sources"] == ["fallback"] * 7 and made["checks"] == list(CHECKS)


def test_how_made_shows_quality_for_users_who_may_see_numbers(code_week):
    made = build_payload(code_week, TARGETS, diet_type="vegetarian", goal="muscle_gain", week_start=MONDAY, numbers_hidden=False)["how_made"]
    assert made["days_ok"] + made["days_with_issues"] == 7 and made["meals_per_day"] == 4
    assert made["emphasis"] == "high_protein" and made["portion_scale"] == 1.0
    assert set(made["average_percent_of_target"]) == {"kcal", "protein", "carbs", "fat"}
    assert 95 <= made["average_percent_of_target"]["kcal"] <= 105


def test_how_made_has_no_numbers_for_hidden_users_and_the_whole_payload_stays_clean(code_week):
    payload = build_payload(code_week, TARGETS, diet_type="vegetarian", goal="fat_loss", week_start=MONDAY, numbers_hidden=True)
    made = payload["how_made"]
    for key in ("days_ok", "days_with_issues", "average_percent_of_target", "emphasis", "portion_scale"):
        assert key not in made
    text = json.dumps(hide_numbers(payload))
    for key in ("kcal", "protein_g", "targets", "average_percent_of_target", "emphasis", "portion_scale", "days_with_issues"):
        assert key not in text, key
    assert hide_numbers(payload)["how_made"]["days_from_code"] == 7                         # the harmless parts remain
    assert made["checks"] == list(CHECKS_HIDDEN)
    assert not any("calorie" in c.lower() or "protein" in c.lower() for c in made["checks"])   # no number-talk for these users


# ---- the active plan view (what the screen reads) ----

PLAN = ("11111111-1111-1111-1111-111111111111", MONDAY, 1, datetime(2026, 11, 8, tzinfo=timezone.utc))
ROWS = [
    (1, "lunch", 2, "Toor dal", 251.0, "katori", 2.0, 256.0, 15.0, 30.0, 5.0),
    (1, "breakfast", 1, "Idli", 160.0, "piece", 4.0, 232.0, 9.4, 43.7, 0.8),
    (1, "lunch", 1, "Roti", 86.0, "piece", 2.0, 174.0, 6.2, 34.2, 0.8),
    (2, "dinner", 1, "Khichdi", 150.0, None, None, 200.0, 7.0, 35.0, 4.0),
]
MADE = {"days_from_model": 3, "days_from_code": 4, "days_ok": 2, "emphasis": "high_protein", "portion_scale": 1.0,
        "average_percent_of_target": {"kcal": 100.0}, "days_with_issues": 5, "checks": ["x"]}


def raw(hidden):
    return {"plan": PLAN, "items": ROWS, "targets": (1800, 100, 225, 56, hidden), "how_made": dict(MADE)}


def test_the_view_groups_by_day_and_meal_in_eating_order_and_sums_each_day():
    view = to_active_meal_plan(raw(False))
    assert [d.day_of_week for d in view.days] == [1, 2]
    assert [m.slot for m in view.days[0].meals] == ["breakfast", "lunch"]                # breakfast before lunch
    assert [i.name for i in view.days[0].meals[1].items] == ["Roti", "Toor dal"]         # by position
    assert view.days[0].meals[1].items[1].text == "2 katori (251 g)" and view.days[1].meals[0].items[0].text == "150 g"
    assert view.days[0].totals == {"kcal": 662.0, "protein_g": 30.6, "carbs_g": 107.9, "fat_g": 6.6}
    assert view.targets == {"kcal": 1800, "protein_g": 100, "carbs_g": 225, "fat_g": 56} and view.numbers_hidden is False
    assert view.how_made["days_ok"] == 2


def test_the_view_removes_every_number_for_hidden_users():
    view = to_active_meal_plan(raw(True))
    assert view.numbers_hidden is True and view.targets is None and all(d.totals is None for d in view.days)
    assert all(i.kcal is None and i.protein_g is None and i.carbs_g is None and i.fat_g is None
               for d in view.days for m in d.meals for i in m.items)
    for key in ("days_ok", "average_percent_of_target", "emphasis", "portion_scale", "days_with_issues"):
        assert key not in view.how_made
    assert view.days[0].meals[0].items[0].text == "4 pieces (160 g)"                     # portions stay


def test_a_missing_how_made_is_fine():
    data = raw(False)
    data["how_made"] = None
    assert to_active_meal_plan(data).how_made is None
