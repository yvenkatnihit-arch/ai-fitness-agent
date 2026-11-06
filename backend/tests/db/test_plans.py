import json

import psycopg.errors
import pytest

pytestmark = pytest.mark.db

# Users can read their own rows; only the backend writes (D-027).
SERVER_WRITTEN = [
    "calculated_targets",
    "meal_plans",
    "meal_plan_items",
    "workout_plans",
    "workout_plan_days",
    "workout_plan_exercises",
    "plan_proposals",
]

MONDAY = "2026-11-09"
TUESDAY = "2026-11-10"


@pytest.mark.parametrize("table", SERVER_WRITTEN)
def test_rls_on_with_only_a_read_own_policy(admin_conn, table):
    assert admin_conn.execute(
        "select relrowsecurity from pg_class where oid = %s::regclass", (f"public.{table}",)
    ).fetchone() == (True,)
    rows = admin_conn.execute(
        "select cmd, roles from pg_policies where schemaname = 'public' and tablename = %s", (table,)
    ).fetchall()
    assert rows == [("SELECT", ["authenticated"])]


@pytest.mark.parametrize("table", SERVER_WRITTEN)
@pytest.mark.parametrize("privilege", ["insert", "update", "delete"])
def test_signed_in_users_cannot_write(admin_conn, table, privilege):
    assert admin_conn.execute(
        "select has_table_privilege('authenticated', %s, %s)", (f"public.{table}", privilege)
    ).fetchone() == (False,)


@pytest.mark.parametrize("table", SERVER_WRITTEN)
def test_signed_out_visitors_cannot_read(admin_conn, table):
    assert admin_conn.execute(
        "select has_table_privilege('anon', %s, 'select')", (f"public.{table}",)
    ).fetchone() == (False,)


# --- Helpers (all run as admin inside the scratch transaction) ---

def expect_rejected(conn, error, sql, params=()):
    with pytest.raises(error):
        with conn.transaction():
            conn.execute(sql, params)


def meal_plan(conn, uid, week=MONDAY, status="pending", approved=False):
    return conn.execute(
        "insert into public.meal_plans (user_id, week_start, status, approved_at)"
        " values (%s, %s, %s, case when %s then now() end) returning id",
        (uid, week, status, approved),
    ).fetchone()[0]


def food(conn):
    return conn.execute(
        "insert into public.foods (name, diet_class, kcal_per_100g, protein_g_per_100g, carbs_g_per_100g,"
        " fat_g_per_100g, source, key) values ('Test roti', 'vegan', 297, 9.8, 46.4, 7.5, 'test', 'test_roti') returning id"
    ).fetchone()[0]


ITEM_INSERT = """
    insert into public.meal_plan_items
      (meal_plan_id, user_id, day_of_week, slot, food_id, grams, kcal, protein_g, carbs_g, fat_g)
    values (%s, %s, 1, 'lunch', %s, 80, 237.6, 7.8, 37.1, 6.0)
"""


# --- Meal plans ---

def test_week_must_start_on_monday(scratch_user):
    conn, uid = scratch_user
    meal_plan(conn, uid, week=MONDAY)
    expect_rejected(conn, psycopg.errors.CheckViolation,
                    "insert into public.meal_plans (user_id, week_start) values (%s, %s)", (uid, TUESDAY))


def test_active_plan_must_have_been_approved(scratch_user):
    conn, uid = scratch_user
    expect_rejected(conn, psycopg.errors.CheckViolation,
                    "insert into public.meal_plans (user_id, week_start, status) values (%s, %s, 'active')",
                    (uid, MONDAY))


def test_only_one_active_meal_plan(scratch_user):
    conn, uid = scratch_user
    meal_plan(conn, uid, week=MONDAY, status="active", approved=True)
    expect_rejected(conn, psycopg.errors.UniqueViolation,
                    "insert into public.meal_plans (user_id, week_start, status, approved_at)"
                    " values (%s, '2026-11-16', 'active', now())", (uid,))


def test_plan_item_cannot_belong_to_another_user(scratch_user, add_user):
    conn, uid = scratch_user
    other = add_user(conn)
    plan_id = meal_plan(conn, uid)
    food_id = food(conn)
    conn.execute(ITEM_INSERT, (plan_id, uid, food_id))  # same user as the plan: fine
    # The composite foreign key (meal_plan_id, user_id) refuses a mismatched owner.
    expect_rejected(conn, psycopg.errors.ForeignKeyViolation, ITEM_INSERT, (plan_id, other, food_id))


def test_food_used_by_a_plan_cannot_be_deleted(scratch_user):
    conn, uid = scratch_user
    food_id = food(conn)
    conn.execute(ITEM_INSERT, (meal_plan(conn, uid), uid, food_id))
    expect_rejected(conn, psycopg.errors.ForeignKeyViolation,
                    "delete from public.foods where id = %s", (food_id,))


# --- Workout plans ---

def test_rep_range_must_be_in_order(scratch_user):
    conn, uid = scratch_user
    plan_id = conn.execute(
        "insert into public.workout_plans (user_id, week_start) values (%s, %s) returning id", (uid, MONDAY)
    ).fetchone()[0]
    day_id = conn.execute(
        "insert into public.workout_plan_days (workout_plan_id, user_id, day_of_week, focus)"
        " values (%s, %s, 1, 'Legs') returning id", (plan_id, uid)
    ).fetchone()[0]
    exercise_id = conn.execute(
        "insert into public.exercises (key, name, muscle_groups, location, difficulty, movement_pattern, form_cues)"
        " values ('test_goblet_squat', 'Test goblet squat', '{quads,glutes}', 'both', 'beginner', 'squat', 'Chest up.')"
        " returning id"
    ).fetchone()[0]
    insert = ("insert into public.workout_plan_exercises (plan_day_id, user_id, exercise_id, position, sets,"
              " reps_min, reps_max, rest_sec) values (%s, %s, %s, %s, 3, %s, %s, 90)")
    conn.execute(insert, (day_id, uid, exercise_id, 1, 8, 12))
    expect_rejected(conn, psycopg.errors.CheckViolation, insert, (day_id, uid, exercise_id, 2, 12, 8))


# --- Proposals ---

PROPOSAL_INSERT = """
    insert into public.plan_proposals (user_id, type, source, summary, payload, status, decided_at)
    values (%s, 'workout_change', 'chat', 'Swap squats for glute bridges today', %s, %s, %s)
"""


def test_proposal_decision_time_matches_status(scratch_user):
    conn, uid = scratch_user
    payload = json.dumps({"swap": {"from": 1, "to": 2}})
    conn.execute(PROPOSAL_INSERT, (uid, payload, "pending", None))
    expect_rejected(conn, psycopg.errors.CheckViolation, PROPOSAL_INSERT, (uid, payload, "approved", None))
    expect_rejected(conn, psycopg.errors.CheckViolation, PROPOSAL_INSERT, (uid, payload, "pending", "2026-11-05"))


# --- Acting as a signed-in user (D-025) ---

def test_user_sees_own_plan_not_others_and_cannot_write(scratch_user, add_user, act_as):
    conn, uid = scratch_user
    other = add_user(conn)
    mine = meal_plan(conn, uid)
    theirs = meal_plan(conn, other)

    act_as(conn, uid)
    visible = {row[0] for row in conn.execute("select id from public.meal_plans").fetchall()}
    assert mine in visible
    assert theirs not in visible  # RLS hides the other user's plan

    expect_rejected(conn, psycopg.errors.InsufficientPrivilege,
                    "update public.meal_plans set status = 'archived' where id = %s", (mine,))
    expect_rejected(conn, psycopg.errors.InsufficientPrivilege,
                    "insert into public.plan_proposals (user_id, type, source, summary, payload)"
                    " values (%s, 'meal_change', 'chat', 'x', '{}')", (uid,))
