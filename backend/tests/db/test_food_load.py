"""The food loader against the real database, inside a transaction that is always rolled back."""

import psycopg
import pytest

from app.core.config import get_settings
from fooddata.load import load_foods, read_validated

pytestmark = pytest.mark.db


@pytest.fixture
def conn():
    connection = psycopg.connect(get_settings().database_url.get_secret_value(), connect_timeout=10)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def test_load_is_idempotent_and_keeps_ids(conn):
    foods = read_validated()
    first = load_foods(conn, foods)
    ids = dict(conn.execute("select key, id from public.foods").fetchall())

    second = load_foods(conn, foods)  # same data again: everything is an update, nothing new
    assert second.inserted == 0 and second.updated == len(foods)
    assert dict(conn.execute("select key, id from public.foods").fetchall()) == ids
    assert first.synonyms == second.synonyms
    assert conn.execute("select count(*) from public.food_synonyms").fetchone()[0] >= first.synonyms


def test_loaded_values_match_the_csv(conn):
    foods = {f.key: f for f in read_validated()}
    load_foods(conn, list(foods.values()))
    row = conn.execute("select kcal_per_100g, diet_class, is_dish, source, review_status "
                       "from public.foods where key = 'idli'").fetchone()
    idli = foods["idli"]
    assert (float(row[0]), row[1], row[2], row[3], row[4]) == (idli.kcal, "vegan", True, "computed", idli.review_status)
    synonyms = {s for (s,) in conn.execute(
        "select synonym from public.food_synonyms s join public.foods f on f.id = s.food_id where f.key = 'curd'")}
    assert {"dahi", "mosaru"} <= synonyms
