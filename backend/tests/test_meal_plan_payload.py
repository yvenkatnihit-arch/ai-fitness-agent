"""The meal plan payload: build, independent verification (tampering), hiding numbers, summary (pure Python)."""

import copy
import json
from datetime import date

import pytest

from app.calc.meal_plan_payload import NUTRITION_KEYS, build_payload, hide_numbers, summarize, verify_payload
from app.calc.meal_solver import DayTargets
from app.llm.client import LLMBusy
from app.workflows.pick_meals import pick_meals
from tests.meal_fixtures import make_foods

FOODS = make_foods()
BY_KEY = {f.key: f for f in FOODS}
TARGETS = DayTargets(1800, 80, 225, 56, 1728, 1872, 92)
MONDAY = date(2026, 11, 9)


def down(prompt):
    raise LLMBusy()


@pytest.fixture(scope="module")
def week():
    return pick_meals(FOODS, "vegetarian", [], TARGETS, "muscle_gain", None, ask=down)


@pytest.fixture
def payload(week):
    return build_payload(week, TARGETS, diet_type="vegetarian", goal="muscle_gain", week_start=MONDAY, numbers_hidden=False)


def check(p, diet="vegetarian", dislikes=()):
    return verify_payload(p, BY_KEY, diet_type=diet, dislikes=dislikes, targets=TARGETS)


def test_the_payload_is_plain_json_with_seven_days(payload):
    json.dumps(payload)                                              # must be storable as jsonb
    assert [d["day_of_week"] for d in payload["days"]] == list(range(1, 8))
    assert payload["kind"] == "meal_plan" and payload["week_start"] == "2026-11-09" and payload["slots"][0] == "breakfast"
    first = payload["days"][0]["items"][0]
    assert {"slot", "role", "position", "food_key", "name", "grams", "unit", "quantity", "text", *NUTRITION_KEYS} <= set(first)


def test_a_freshly_built_payload_verifies(payload):
    assert check(payload) == []


def test_positions_count_from_one_inside_each_meal(payload):
    for day in payload["days"]:
        for slot in payload["slots"]:
            assert [i["position"] for i in day["items"] if i["slot"] == slot] == list(
                range(1, 1 + sum(i["slot"] == slot for i in day["items"])))


def mutate(payload, change):
    p = copy.deepcopy(payload)
    change(p)
    return check(p)


@pytest.mark.parametrize("change,fragment", [
    (lambda p: p["days"][0]["items"][0].update(grams=900.0), "numbers do not match the food data"),       # inflated portion
    (lambda p: p["days"][0]["items"][0].update(kcal=1.0), "numbers do not match the food data"),         # fake low calories
    (lambda p: p["days"][0]["items"][0].update(grams=-5), "grams must be above 0"),
    (lambda p: p["days"][0]["items"][0].update(grams=5000), "grams must be above 0 and at most 2000"),
    (lambda p: p["days"][0]["items"][0].update(grams="lots"), "grams must be above 0"),
    (lambda p: p["days"][0]["items"][0].update(food_key="invented_curry"), "not in the food database"),
    (lambda p: p["days"][0]["items"][0].update(food_key="egg"), "is not allowed for a vegetarian diet"),   # egg is eggetarian
    (lambda p: p["days"][0]["items"][0].update(unit="katori", quantity=None), "unit and quantity go together"),
    (lambda p: p["days"][0]["items"][0].update(unit="piece", quantity=None), "unit and quantity go together"),
    (lambda p: p["days"][1]["items"].pop(0), "outside the safe range"),
    (lambda p: p["days"][1].update(items=[]), "no meals"),
    (lambda p: p["days"][2]["items"][1].update(position=9), "wrong order of items"),
    (lambda p: p["days"].pop(), "exactly seven days"),
    (lambda p: p.update(kind="workout_plan"), "not a meal plan"),
    (lambda p: p.update(slots=["breakfast", "dinner"]), "not a known set"),
])
def test_tampering_is_caught(payload, change, fragment):
    assert any(fragment in problem for problem in mutate(payload, change)), mutate(payload, change)


def test_a_household_unit_must_match_the_grams(payload):
    def lie(p):
        item = next(i for i in p["days"][0]["items"] if i["unit"] == "katori")
        item["quantity"] = item["quantity"] + 1                      # says one more katori than the grams
    assert any("does not match" in x for x in mutate(payload, lie))


def test_a_unit_the_food_does_not_have_is_refused(payload):
    def lie(p):
        item = next(i for i in p["days"][0]["items"] if i["unit"] == "katori")
        item["unit"] = "glass"
    assert any("is not measured in 'glass'" in x for x in mutate(payload, lie))


def test_the_plan_is_checked_against_the_users_own_diet_and_dislikes(payload):
    used = {i["food_key"] for d in payload["days"] for i in d["items"]}
    assert check(payload, diet="vegan")                              # a vegetarian plan is NOT fine for a vegan
    dislike = BY_KEY[sorted(used)[0]].name.split()[0]
    assert any("disliked list" in x for x in check(payload, dislikes=[dislike]))


def test_the_calorie_band_is_enforced_from_the_users_targets_not_the_payloads(payload):
    day1 = payload["days"][0]["totals"]["kcal"]
    stricter = DayTargets(1800, 80, 225, 56, day1 + 50, day1 + 100, 92)           # a personal band that excludes day 1
    problems = verify_payload(payload, BY_KEY, diet_type="vegetarian", dislikes=[], targets=stricter)
    assert any(p.startswith("day 1:") and "outside the safe range" in p for p in problems)
    cap = DayTargets(1800, 80, 225, 56, 1728, 1872, 20)                           # a protein cap far below what the plan has
    assert any("above the 20 g limit" in p for p in verify_payload(payload, BY_KEY, diet_type="vegetarian", dislikes=[], targets=cap))


@pytest.mark.parametrize("junk", [None, [], "plan", 5, {"kind": "meal_plan"}, {"kind": "meal_plan", "days": "x"}])
def test_junk_is_not_a_plan(junk):
    assert check(junk)


def test_hiding_numbers_removes_every_calorie_and_macro(week):
    p = build_payload(week, TARGETS, diet_type="vegetarian", goal="fat_loss", week_start=MONDAY, numbers_hidden=True)
    hidden = hide_numbers(p)
    text = json.dumps(hidden)
    for key in ("kcal", "protein_g", "carbs_g", "fat_g", "targets", "totals", "percent_of_target", "issues", "status", "emphasis", "portion_scale"):
        assert f'"{key}"' not in text, key
    assert "issues" not in text and "high_protein" not in text      # not even as a value
    assert hidden["days"][0]["items"][0]["grams"] > 0 and hidden["days"][0]["items"][0]["text"]     # portions stay
    assert "kcal" in json.dumps(p) and p["days"][0]["items"][0]["kcal"] > 0                          # the original is untouched


def test_the_summary_has_no_numbers_when_they_must_be_hidden(payload):
    assert summarize(payload) == "7-day vegetarian meal plan, 4 meals a day, about 1800 kcal a day, starting 2026-11-09."
    hidden = copy.deepcopy(payload)
    hidden["numbers_hidden"] = True
    text = summarize(hidden)
    assert "kcal" not in text and "balanced meals" in text and len(text) <= 500
