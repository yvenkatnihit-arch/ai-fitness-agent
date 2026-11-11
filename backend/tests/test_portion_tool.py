"""Step 7.8b: the portion_nutrition tool (code does the maths), with a fake database. No LLM, no network."""

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest

from app.agents import food_tools
from app.agents.context import RunContext
from app.agents.food_tools import PORTION_NUTRITION, PortionArgs
from app.agents.nutrition import NUTRITION_SPEC, nutrition_registry
from app.agents.runner import ToolCall, Turn, build_specialist
from app.calc.portions import Per100g
from app.db.meals import LoggableFood

ROTI = LoggableFood(1, "Roti / chapati (no fat)", Per100g(202.0, 7.3, 40.2, 2.5), {"piece": 43.0})
PANEER = LoggableFood(2, "Paneer", Per100g(265.0, 18.3, 1.2, 20.8), {"piece": 30.0, "katori": 100.0})


@pytest.fixture
def fake_db(monkeypatch):
    seen = []

    @contextmanager
    def tx(user_id):
        seen.append(user_id)
        yield object()
    foods = {"roti": ROTI, "paneer": PANEER}
    monkeypatch.setattr(food_tools, "user_transaction", tx)
    monkeypatch.setattr(food_tools.repo, "get_food_for_portion", lambda conn, key: foods.get(key))
    return seen


def run(**args):
    return PORTION_NUTRITION.run(RunContext(uuid4()), PortionArgs(**args))


def test_grams_come_from_the_quantity_and_nutrition_from_the_shared_calculator(fake_db):
    assert run(food_key="paneer", quantity=150, unit="g") == {
        "food": "Paneer", "amount": "150 g", "grams": 150.0, "kcal": 397.5, "protein_g": 27.5, "carbs_g": 1.8, "fat_g": 31.2}


def test_household_units_are_turned_into_grams_first(fake_db):
    out = run(food_key="roti", quantity=3, unit="piece")
    assert out["grams"] == 129.0 and out["kcal"] == 260.6 and out["protein_g"] == 9.4 and out["amount"] == "3 piece"


def test_the_unit_defaults_to_grams_and_fractions_work(fake_db):
    assert run(food_key="paneer", quantity=50)["grams"] == 50.0
    assert run(food_key="paneer", quantity=1.5, unit="katori")["grams"] == 150.0


def test_it_runs_as_the_user_under_rls(fake_db):
    uid = uuid4()
    PORTION_NUTRITION.run(RunContext(uid), PortionArgs(food_key="paneer", quantity=10))
    assert fake_db == [uid]


def test_an_unknown_unit_lists_the_valid_ones_instead_of_guessing(fake_db):
    out = run(food_key="roti", quantity=2, unit="cup")
    assert "kcal" not in out and out["available_units"] == ["g", "piece"] and "can't be measured in 'cup'" in out["error"]


def test_an_unknown_food_key_is_an_error_not_a_guess(fake_db):
    assert run(food_key="made_up", quantity=100) == {"error": "Unknown food key. Use a key returned by search_foods."}


def test_an_amount_above_the_item_limit_is_refused_by_the_calculator(fake_db):
    out = run(food_key="paneer", quantity=3000, unit="katori")       # 300,000 g
    assert "error" in out and "kcal" not in out


@pytest.mark.parametrize("args", [{"food_key": "x", "quantity": 0}, {"food_key": "x", "quantity": -5}, {"food_key": "x", "quantity": 3001},
                                  {"food_key": "", "quantity": 1}, {"food_key": "x", "quantity": 1, "unit": ""},
                                  {"food_key": "x", "quantity": 1, "user_id": "someone"}, {"quantity": 1}])
def test_the_arguments_are_strict(args):
    with pytest.raises(ValueError):
        PortionArgs(**args)


def test_the_tool_is_read_only_and_on_the_specialists_allowlist():
    assert PORTION_NUTRITION.scope == "read" and "portion_nutrition" in NUTRITION_SPEC.tools
    assert nutrition_registry().names() == {"search_foods", "portion_nutrition", "find_foods"}


def test_a_specialist_can_search_then_calculate_then_answer_with_the_tools_numbers(fake_db, monkeypatch):
    monkeypatch.setattr(food_tools.repo, "search_foods", lambda conn, q, limit: [{
        "key": "paneer", "name": "Paneer", "diet_class": "vegetarian", "kcal": 265, "protein_g": 18.3, "carbs_g": 1.2, "fat_g": 20.8, "units": []}])
    turns = iter([Turn(call=ToolCall("search_foods", {"query": "paneer"}), tokens=10),
                  Turn(call=ToolCall("portion_nutrition", {"food_key": "paneer", "quantity": 150, "unit": "g"}), tokens=10),
                  Turn(final="150 g of paneer has 397.5 kcal.", tokens=10)])
    model_saw = []

    def model(messages):
        model_saw.append(messages)
        return next(turns)
    r = build_specialist(NUTRITION_SPEC, nutrition_registry(), model).run("calories in 150 g paneer?", RunContext(uuid4()))
    assert r.status == "ok" and [(t.name, t.outcome) for t in r.tools] == [("search_foods", "ok"), ("portion_nutrition", "ok")]
    assert "397.5" in json.dumps(model_saw[-1][-1]["content"])      # the model was handed the calculated number, it did not compute it
    assert r.steps == 3 <= NUTRITION_SPEC.max_steps


def test_the_model_cannot_pass_a_user_id_to_the_calculator(fake_db):
    turns = iter([Turn(call=ToolCall("portion_nutrition", {"food_key": "paneer", "quantity": 1, "user_id": str(uuid4())})), Turn(final="ok")])
    r = build_specialist(NUTRITION_SPEC, nutrition_registry(), lambda m: next(turns)).run("x", RunContext(uuid4()))
    assert r.tools[0].outcome == "bad_args" and fake_db == []
