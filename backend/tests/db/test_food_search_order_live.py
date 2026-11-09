"""Step 7.8a (D-083): the food search ORDER on the real data, for the queries the nutrition eval found wrong.
Needs `uv run python -m fooddata.load` to have been run."""

import pytest

from app.db.foods import search_foods

pytestmark = pytest.mark.db


@pytest.fixture
def user_conn(scratch_user, act_as):
    conn, uid = scratch_user
    act_as(conn, uid)
    return conn


def names(conn, query, limit=5):
    return [f["name"] for f in search_foods(conn, query, limit)]


def test_milk_lists_plain_milk_first(user_conn):
    top = names(user_conn, "milk", 2)
    assert all(n.startswith("Milk (") for n in top), top


def test_roti_lists_roti_before_bread(user_conn):
    top = names(user_conn, "roti", 3)
    assert top[0].startswith("Roti"), top
    assert "White bread" not in top[:2]


def test_cooked_rice_lists_rice_before_dals(user_conn):
    top = names(user_conn, "cooked rice", 3)
    assert all("rice" in n.lower() for n in top), top


def test_a_two_word_query_finds_foods_that_have_only_one_of_the_words(user_conn):
    assert "Steamed white rice" in names(user_conn, "cooked rice", 5)


def test_exact_two_word_names_still_come_first(user_conn):
    assert names(user_conn, "boiled egg", 1) == ["Boiled egg"]
    assert names(user_conn, "toor dal", 1)[0].startswith("Toor dal")
    assert names(user_conn, "chana dal", 2)[0].startswith("Chana dal")


def test_single_word_queries_still_work(user_conn):
    assert names(user_conn, "paneer", 1) == ["Paneer"]
    assert names(user_conn, "idli", 1) == ["Idli"]
    assert names(user_conn, "chawal", 1)[0] == "Steamed white rice"
