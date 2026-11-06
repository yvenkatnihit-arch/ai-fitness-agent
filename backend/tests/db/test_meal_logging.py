"""Meal logging repo functions against the real database, as a scratch user (always rolled back).
Needs the food data loaded (`uv run python -m fooddata.load`)."""

import uuid
from datetime import date

import pytest

from app.calc.portions import grams_for, nutrition_for
from app.db import meals as repo

pytestmark = pytest.mark.db
DAY = date(2026, 11, 6)


def food_id(conn, key):
    return conn.execute("select id from public.foods where key = %s", (key,)).fetchone()[0]


def log(conn, *portions, slot="lunch"):
    ids = [food_id(conn, key) for key, _, _ in portions]
    foods = repo.foods_for_logging(conn, ids)
    items = []
    for fid, (_, quantity, unit) in zip(ids, portions):
        grams = grams_for(quantity, unit, foods[fid].unit_grams)
        items.append(repo.NewItem(fid, quantity, unit, grams, nutrition_for(grams, foods[fid].per_100g)))
    return repo.insert_meal(conn, DAY, slot, "form", items)


@pytest.fixture
def user_conn(scratch_user, act_as):
    conn, uid = scratch_user
    act_as(conn, uid)
    return conn


def test_logged_meal_reads_back_with_computed_snapshot(user_conn):
    log(user_conn, ("roti", 2, "piece"), ("sambar", 1, "katori"))
    [meal] = repo.meals_on(user_conn, DAY)
    roti, sambar = meal["items"]
    assert (roti["grams"], sambar["grams"]) == (86.0, 152.8)
    assert roti["kcal"] == pytest.approx(173.7)   # 86 g x 202 kcal / 100
    assert meal["source"] == "form"


def test_household_units_come_from_the_database(user_conn):
    foods = repo.foods_for_logging(user_conn, [food_id(user_conn, "idli")])
    assert next(iter(foods.values())).unit_grams == {"piece": 40.0}


def test_other_users_cannot_see_or_delete_my_meal(user_conn, act_as):
    meal_id = log(user_conn, ("roti", 1, "piece"))
    stranger = uuid.uuid4()
    user_conn.execute("reset role")
    user_conn.execute("insert into auth.users (id, email) values (%s, %s)", (stranger, f"s-{stranger}@example.test"))
    user_conn.execute("insert into public.profiles (id) values (%s)", (stranger,))
    act_as(user_conn, stranger)
    assert repo.meals_on(user_conn, DAY) == []
    assert repo.delete_meal(user_conn, meal_id) is False


def test_delete_removes_the_meal_and_its_items(user_conn):
    meal_id = log(user_conn, ("roti", 1, "piece"), ("idli", 2, "piece"))
    assert repo.delete_meal(user_conn, meal_id) is True
    assert repo.meals_on(user_conn, DAY) == []
    assert user_conn.execute("select count(*) from public.meal_log_items where meal_log_id = %s",
                             (meal_id,)).fetchone()[0] == 0
