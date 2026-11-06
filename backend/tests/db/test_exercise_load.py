"""The exercise loader against the real database, inside a transaction that is always rolled back."""

import psycopg
import pytest

from app.core.config import get_settings
from exercisedata.load import load_exercises, read_validated

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
    exercises = read_validated()
    load_exercises(conn, exercises)
    ids = dict(conn.execute("select key, id from public.exercises").fetchall())

    second = load_exercises(conn, exercises)  # same data again: everything is an update, nothing new
    assert second.inserted == 0 and second.updated == len(exercises)
    assert dict(conn.execute("select key, id from public.exercises").fetchall()) == ids


def test_loaded_values_match_the_csv(conn):
    exercises = {e.key: e for e in read_validated()}
    load_exercises(conn, list(exercises.values()))
    row = conn.execute("select name, equipment, location, movement_pattern, contraindications, form_cues, source_ref "
                       "from public.exercises where key = 'barbell_back_squat'").fetchone()
    squat = exercises["barbell_back_squat"]
    assert row[0] == squat.name and row[1] == ["barbell"] and row[2] == "gym" and row[3] == "squat"
    assert set(row[4]) == {"knee", "lower_back"}
    assert row[5].count("\n") >= 1 and row[6] == "Barbell_Full_Squat"
    bodyweight = conn.execute("select equipment from public.exercises where key = 'plank'").fetchone()[0]
    assert bodyweight == []  # no equipment is an empty list, not null
