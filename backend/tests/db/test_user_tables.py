from decimal import Decimal

import psycopg.errors
import pytest

pytestmark = pytest.mark.db

# Every user-owned table and the exact policies it should have.
EXPECTED_POLICIES = {
    "profiles": {"SELECT", "INSERT", "UPDATE"},
    "health_screening": {"SELECT", "INSERT", "UPDATE"},
    "goals": {"SELECT", "INSERT", "UPDATE"},
    "calculated_targets": {"SELECT"},  # server-written (D-027): users read, backend inserts
}


@pytest.mark.parametrize("table", EXPECTED_POLICIES)
def test_rls_enabled(admin_conn, table):
    row = admin_conn.execute(
        "select relrowsecurity from pg_class where oid = %s::regclass", (f"public.{table}",)
    ).fetchone()
    assert row == (True,)


@pytest.mark.parametrize(("table", "commands"), EXPECTED_POLICIES.items())
def test_policies(admin_conn, table, commands):
    rows = admin_conn.execute(
        "select cmd, roles from pg_policies where schemaname = 'public' and tablename = %s", (table,)
    ).fetchall()
    assert {cmd for cmd, _ in rows} == commands
    assert all(roles == ["authenticated"] for _, roles in rows)  # never anon or public


@pytest.mark.parametrize("table", EXPECTED_POLICIES)
def test_anon_has_no_access(admin_conn, table):
    row = admin_conn.execute(
        "select has_table_privilege('anon', %s, 'select') or has_table_privilege('anon', %s, 'insert')",
        (f"public.{table}", f"public.{table}"),
    ).fetchone()
    assert row == (False,)


# --- Constraints really reject bad data (each test rolls back everything) ---

def expect_rejected(conn, error, sql, params):
    with pytest.raises(error):
        with conn.transaction():  # savepoint, so the scratch transaction stays usable
            conn.execute(sql, params)


def test_profile_rejects_height_in_metres(scratch_user):
    conn, uid = scratch_user
    expect_rejected(conn, psycopg.errors.CheckViolation,
                    "update public.profiles set height_cm = 1.8 where id = %s", (uid,))


def test_profile_rejects_onboarding_without_consent(scratch_user):
    conn, uid = scratch_user
    expect_rejected(conn, psycopg.errors.CheckViolation,
                    "update public.profiles set onboarded_at = now() where id = %s", (uid,))


def test_screening_rejects_unknown_injury_area(scratch_user):
    conn, uid = scratch_user
    expect_rejected(conn, psycopg.errors.CheckViolation,
                    "insert into public.health_screening (user_id, injury_areas) values (%s, '{toe}')", (uid,))


def test_screening_accepts_valid_row(scratch_user):
    conn, uid = scratch_user
    conn.execute(
        "insert into public.health_screening (user_id, kidney, injury_areas) values (%s, true, '{knee}')", (uid,)
    )
    assert conn.execute(
        "select kidney, diabetes from public.health_screening where user_id = %s", (uid,)
    ).fetchone() == (True, False)


def test_only_one_active_goal(scratch_user):
    conn, uid = scratch_user
    insert = "insert into public.goals (user_id, goal_type, start_weight_kg) values (%s, %s, 80)"
    conn.execute(insert, (uid, "fat_loss"))
    expect_rejected(conn, psycopg.errors.UniqueViolation, insert, (uid, "muscle_gain"))


def test_inactive_goals_can_pile_up(scratch_user):
    conn, uid = scratch_user
    for goal in ("fat_loss", "recomp"):
        conn.execute(
            "insert into public.goals (user_id, goal_type, start_weight_kg, active) values (%s, %s, 80, false)",
            (uid, goal),
        )
    conn.execute("insert into public.goals (user_id, goal_type, start_weight_kg) values (%s, 'muscle_gain', 80)", (uid,))


TARGET_INSERT = """
    insert into public.calculated_targets
      (user_id, bmr_kcal, tdee_kcal, goal_target_kcal, calorie_target_kcal, protein_g, fat_g, carbs_g)
    values (%s, 1780, 2759, 2207.2, %s, 160, 61.3, 253.9)
"""


def test_targets_reject_below_calorie_floor(scratch_user):
    conn, uid = scratch_user
    expect_rejected(conn, psycopg.errors.CheckViolation, TARGET_INSERT, (uid, 900))


def test_targets_accept_engine_output(scratch_user):
    conn, uid = scratch_user
    conn.execute(TARGET_INSERT, (uid, 2207.2))
    # Postgres numeric comes back as Python Decimal (exact), stored to 1 decimal place.
    assert conn.execute(
        "select calorie_target_kcal from public.calculated_targets where user_id = %s", (uid,)
    ).fetchone() == (Decimal("2207.2"),)


def test_updated_at_changes_on_update(scratch_user):
    conn, uid = scratch_user
    # Start from an old timestamp, so we can see the trigger move it forward.
    conn.execute(
        "insert into public.health_screening (user_id, updated_at) values (%s, '2020-01-01')", (uid,)
    )
    conn.execute("update public.health_screening set diabetes = true where user_id = %s", (uid,))
    moved = conn.execute(
        "select updated_at > '2020-01-02' from public.health_screening where user_id = %s", (uid,)
    ).fetchone()
    assert moved == (True,)
