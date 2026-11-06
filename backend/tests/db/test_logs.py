import psycopg.errors
import pytest

pytestmark = pytest.mark.db

USER_WRITTEN_LOGS = ["meal_logs", "meal_log_items", "workout_logs", "workout_log_sets", "body_weight_entries"]


@pytest.mark.parametrize("table", USER_WRITTEN_LOGS)
def test_logs_have_one_own_rows_policy_for_everything(admin_conn, table):
    assert admin_conn.execute(
        "select relrowsecurity from pg_class where oid = %s::regclass", (f"public.{table}",)
    ).fetchone() == (True,)
    rows = admin_conn.execute(
        "select cmd, roles from pg_policies where schemaname = 'public' and tablename = %s", (table,)
    ).fetchall()
    assert rows == [("ALL", ["authenticated"])]


def test_weekly_checkins_are_read_only_for_users(admin_conn):
    rows = admin_conn.execute(
        "select cmd from pg_policies where schemaname = 'public' and tablename = 'weekly_checkins'"
    ).fetchall()
    assert rows == [("SELECT",)]
    assert admin_conn.execute(
        "select has_table_privilege('authenticated', 'public.weekly_checkins', 'insert')"
    ).fetchone() == (False,)


@pytest.mark.parametrize("table", USER_WRITTEN_LOGS + ["weekly_checkins"])
def test_signed_out_visitors_cannot_read(admin_conn, table):
    assert admin_conn.execute(
        "select has_table_privilege('anon', %s, 'select')", (f"public.{table}",)
    ).fetchone() == (False,)


# --- Helpers ---

def expect_rejected(conn, error, sql, params=()):
    with pytest.raises(error):
        with conn.transaction():
            conn.execute(sql, params)


WEIGHT_INSERT = "insert into public.body_weight_entries (user_id, measured_on, weight_kg) values (%s, %s, %s)"


def food(conn):
    return conn.execute(
        "insert into public.foods (name, diet_class, kcal_per_100g, protein_g_per_100g, carbs_g_per_100g,"
        " fat_g_per_100g, source, key) values ('Test curd', 'vegetarian', 60, 3.1, 4.4, 3.4, 'test', 'test_curd') returning id"
    ).fetchone()[0]


# --- Constraints ---

def test_one_weight_entry_per_day(scratch_user):
    conn, uid = scratch_user
    conn.execute(WEIGHT_INSERT, (uid, "2026-11-05", 80.4))
    expect_rejected(conn, psycopg.errors.UniqueViolation, WEIGHT_INSERT, (uid, "2026-11-05", 80.1))


def test_weight_typo_is_refused(scratch_user):
    conn, uid = scratch_user
    # 800 kg: extra digits typed. Range is 30-300 kg (D-019).
    expect_rejected(conn, psycopg.errors.CheckViolation, WEIGHT_INSERT, (uid, "2026-11-05", 800))


def test_meal_item_cannot_belong_to_another_user(scratch_user, add_user):
    conn, uid = scratch_user
    other = add_user(conn)
    log_id = conn.execute(
        "insert into public.meal_logs (user_id, logged_on, slot, source) values (%s, '2026-11-05', 'lunch', 'form')"
        " returning id", (uid,)
    ).fetchone()[0]
    insert = ("insert into public.meal_log_items (meal_log_id, user_id, food_id, quantity, unit, grams,"
              " kcal, protein_g, carbs_g, fat_g) values (%s, %s, %s, 1, 'katori', 150, 90, 4.7, 6.6, 5.1)")
    food_id = food(conn)
    conn.execute(insert, (log_id, uid, food_id))
    expect_rejected(conn, psycopg.errors.ForeignKeyViolation, insert, (log_id, other, food_id))


def test_workout_log_survives_plan_deletion(scratch_user):
    conn, uid = scratch_user
    plan_id = conn.execute(
        "insert into public.workout_plans (user_id, week_start) values (%s, '2026-11-02') returning id", (uid,)
    ).fetchone()[0]
    day_id = conn.execute(
        "insert into public.workout_plan_days (workout_plan_id, user_id, day_of_week) values (%s, %s, 4) returning id",
        (plan_id, uid),
    ).fetchone()[0]
    log_id = conn.execute(
        "insert into public.workout_logs (user_id, logged_on, plan_day_id, source) values (%s, '2026-11-05', %s, 'form')"
        " returning id", (uid, day_id)
    ).fetchone()[0]

    conn.execute("delete from public.workout_plans where id = %s", (plan_id,))
    # The log is kept; only the link to the deleted plan day is cleared.
    assert conn.execute(
        "select plan_day_id, user_id from public.workout_logs where id = %s", (log_id,)
    ).fetchone() == (None, uid)


def test_checkin_never_adjusts_with_too_few_weigh_ins(scratch_user):
    conn, uid = scratch_user
    insert = ("insert into public.weekly_checkins (user_id, week_start, weigh_in_count, decision)"
              " values (%s, %s, %s, %s)")
    conn.execute(insert, (uid, "2026-11-02", 3, "need_data"))
    expect_rejected(conn, psycopg.errors.CheckViolation, insert, (uid, "2026-11-09", 3, "adjust"))
    conn.execute(insert, (uid, "2026-11-16", 5, "adjust"))


# --- Acting as a signed-in user (D-025) ---

def test_user_can_log_read_and_delete_own_weight(scratch_user, act_as):
    conn, uid = scratch_user
    act_as(conn, uid)
    conn.execute(WEIGHT_INSERT, (uid, "2026-11-05", 80.4))
    assert conn.execute("select count(*) from public.body_weight_entries").fetchone() == (1,)
    conn.execute("delete from public.body_weight_entries where measured_on = '2026-11-05'")
    assert conn.execute("select count(*) from public.body_weight_entries").fetchone() == (0,)


def test_user_cannot_log_for_someone_else(scratch_user, add_user, act_as):
    conn, uid = scratch_user
    other = add_user(conn)
    act_as(conn, uid)
    # RLS "with check" refuses a row whose user_id isn't the signed-in user.
    expect_rejected(conn, psycopg.errors.InsufficientPrivilege, WEIGHT_INSERT, (other, "2026-11-05", 70))


def test_user_cannot_see_or_delete_others_logs(scratch_user, add_user, act_as):
    conn, uid = scratch_user
    other = add_user(conn)
    conn.execute(WEIGHT_INSERT, (other, "2026-11-05", 70))  # as admin

    act_as(conn, uid)
    assert conn.execute("select count(*) from public.body_weight_entries").fetchone() == (0,)
    deleted = conn.execute("delete from public.body_weight_entries where user_id = %s", (other,)).rowcount
    assert deleted == 0  # RLS makes the other user's rows invisible, so nothing is deleted
