"""Step 7.8b: portion_nutrition against the real foods table, as a signed-in user under RLS (rolled back afterwards)."""

from contextlib import contextmanager

import pytest

from app.agents import food_tools
from app.agents.context import RunContext
from app.agents.food_tools import PortionArgs, SearchFoodsArgs
from app.calc.portions import Per100g, nutrition_for
from app.db import foods as repo

pytestmark = pytest.mark.db


@pytest.fixture
def user_conn(scratch_user, act_as):
    conn, uid = scratch_user
    act_as(conn, uid)
    return conn


def test_a_food_is_found_by_key_with_its_per_100g_values(user_conn):
    food = repo.get_food_for_portion(user_conn, "paneer")
    assert food is not None and food.name == "Paneer" and food.per_100g.kcal > 0


def test_a_household_unit_resolves_to_its_stored_grams(user_conn):
    key = repo.search_foods(user_conn, "roti", 1)[0]["key"]
    food = repo.get_food_for_portion(user_conn, key)
    assert food.unit_grams.get("piece", 0) > 0


def test_an_unknown_key_is_none(user_conn):
    assert repo.get_food_for_portion(user_conn, "no_such_food_key") is None


def test_the_tools_search_then_portion_agree_with_the_shared_calculator(scratch_user, act_as, monkeypatch):
    """The tools open their own user_transaction: point it at this test's rolled-back connection."""
    conn, uid = scratch_user

    @contextmanager
    def tx(user_id):
        act_as(conn, user_id)
        yield conn
    monkeypatch.setattr(food_tools, "user_transaction", tx)
    ctx = RunContext(uid)
    found = food_tools._search(ctx, SearchFoodsArgs(query="roti", limit=1))["foods"][0]
    unit = found["units"][0]
    out = food_tools._portion(ctx, PortionArgs(food_key=found["key"], quantity=2, unit=unit["unit"]))
    p = found["per_100g"]
    expected = nutrition_for(round(2 * unit["grams"], 1), Per100g(p["kcal"], p["protein_g"], p["carbs_g"], p["fat_g"]))
    assert out["grams"] == round(2 * unit["grams"], 1) and out["kcal"] == expected.kcal and out["protein_g"] == expected.protein_g
