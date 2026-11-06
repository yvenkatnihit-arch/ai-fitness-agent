"""Food search against the loaded food data, as a signed-in user under RLS (rolled back afterwards).
Needs `uv run python -m fooddata.load` to have been run."""

import pytest

from app.db.foods import search_foods

pytestmark = pytest.mark.db


@pytest.fixture
def user_conn(scratch_user, act_as):
    conn, uid = scratch_user
    act_as(conn, uid)
    return conn


def keys(conn, query, limit=10):
    return [f["key"] for f in search_foods(conn, query, limit)]


def test_local_name_finds_the_food(user_conn):
    assert keys(user_conn, "dahi")[0] == "curd"


def test_chawal_means_cooked_rice_first(user_conn):
    results = keys(user_conn, "chawal")
    assert results[0] == "rice_cooked"
    assert results.index("rice_cooked") < results.index("rice_white")


def test_misspelling_still_finds_the_food(user_conn):
    assert "toor_dal" in keys(user_conn, "toor dhal")


def test_results_include_household_units(user_conn):
    idli = search_foods(user_conn, "idli", 5)[0]
    assert idli["key"] == "idli"
    assert {"unit": "piece", "grams": 40.0} in idli["units"]


def test_like_wildcards_are_literal(user_conn):
    assert keys(user_conn, "%%") == []  # '%' must not match every food


def test_limit_is_respected(user_conn):
    assert len(keys(user_conn, "dal", limit=3)) == 3


@pytest.mark.parametrize(("typed", "expected"), [("chapathi", "roti"), ("panner", "paneer"),
                                                  ("biriyani", "chicken_biryani"), ("sambhar", "sambar")])
def test_common_misspellings(user_conn, typed, expected):
    assert expected in keys(user_conn, typed)


def test_rice_does_not_drag_in_ice_cream(user_conn):
    assert not any("ice cream" in f["name"].lower() for f in search_foods(user_conn, "rice", 25))


def test_dal_lists_dals_not_dalda(user_conn):
    top = search_foods(user_conn, "dal", 5)
    assert all("dal" in f["name"].lower().split() or "dal" in " ".join(f["synonyms"]).lower().split() for f in top)
