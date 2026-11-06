import psycopg.errors
import pytest

pytestmark = pytest.mark.db

REFERENCE_TABLES = ["foods", "food_synonyms", "food_units", "exercises"]


@pytest.mark.parametrize("table", REFERENCE_TABLES)
def test_rls_on_with_a_single_read_policy(admin_conn, table):
    assert admin_conn.execute(
        "select relrowsecurity from pg_class where oid = %s::regclass", (f"public.{table}",)
    ).fetchone() == (True,)
    rows = admin_conn.execute(
        "select cmd, roles, qual from pg_policies where schemaname = 'public' and tablename = %s", (table,)
    ).fetchall()
    assert rows == [("SELECT", ["authenticated"], "true")]


@pytest.mark.parametrize("table", REFERENCE_TABLES)
@pytest.mark.parametrize("privilege", ["insert", "update", "delete"])
def test_signed_in_users_cannot_write(admin_conn, table, privilege):
    assert admin_conn.execute(
        "select has_table_privilege('authenticated', %s, %s)", (f"public.{table}", privilege)
    ).fetchone() == (False,)


@pytest.mark.parametrize("table", REFERENCE_TABLES)
def test_signed_out_visitors_cannot_read(admin_conn, table):
    assert admin_conn.execute(
        "select has_table_privilege('anon', %s, 'select')", (f"public.{table}",)
    ).fetchone() == (False,)


# --- Behaviour, inside a rolled-back transaction ---

FOOD_INSERT = """
    insert into public.foods (name, diet_class, kcal_per_100g, protein_g_per_100g,
                              carbs_g_per_100g, fat_g_per_100g, source, key)
    values (%s, 'vegan', %s, %s, %s, %s, 'test', 'test_' || substr(md5(random()::text), 1, 12))
    returning id
"""


def test_signed_in_user_can_read_but_not_write(scratch_user, act_as):
    conn, uid = scratch_user
    food_id = conn.execute(FOOD_INSERT, ("Test dal", 116, 6.8, 18.0, 1.5)).fetchone()[0]  # as admin

    act_as(conn, uid)
    assert conn.execute("select name from public.foods where id = %s", (food_id,)).fetchone() == ("Test dal",)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with conn.transaction():
            conn.execute(FOOD_INSERT, ("Sneaky food", 100, 1, 1, 1))


def test_food_rejects_more_macros_than_fit_in_100g(scratch_user):
    conn, _ = scratch_user
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute(FOOD_INSERT, ("Impossible food", 400, 60, 60, 10))


def test_exercise_rejects_unknown_contraindication(scratch_user):
    conn, _ = scratch_user
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute(
                """insert into public.exercises (name, muscle_groups, location, difficulty,
                                                 movement_pattern, form_cues, contraindications)
                   values ('Test squat', '{quads}', 'both', 'beginner', 'squat', 'Knees over toes.', '{toe}')"""
            )


def test_fuzzy_search_finds_close_spellings(scratch_user):
    conn, _ = scratch_user
    conn.execute(FOOD_INSERT, ("Toor dal, cooked", 116, 6.8, 18.0, 1.5))
    # similarity() is 0..1: how many 3-letter chunks ("trigrams") the two strings share.
    row = conn.execute(
        "select extensions.similarity(name, %s) from public.foods where name = 'Toor dal, cooked'",
        ("toor dhal",),
    ).fetchone()
    assert row[0] > 0.3  # pg_trgm's default "similar enough" threshold
