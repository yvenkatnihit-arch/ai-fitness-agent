from decimal import Decimal

import psycopg.errors
import pytest

pytestmark = pytest.mark.db

READ_OWN = ["conversations", "messages", "conversation_summaries", "usage_counters"]


@pytest.mark.parametrize("table", READ_OWN)
def test_chat_tables_are_read_own_only(admin_conn, table):
    assert admin_conn.execute(
        "select relrowsecurity from pg_class where oid = %s::regclass", (f"public.{table}",)
    ).fetchone() == (True,)
    assert admin_conn.execute(
        "select cmd, roles from pg_policies where schemaname = 'public' and tablename = %s", (table,)
    ).fetchall() == [("SELECT", ["authenticated"])]
    assert admin_conn.execute(
        "select has_table_privilege('authenticated', %s, 'insert')", (f"public.{table}",)
    ).fetchone() == (False,)


@pytest.mark.parametrize("relation", ["agent_runs", "daily_llm_cost"])
@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_cost_data_is_admin_only(admin_conn, relation, role):
    assert admin_conn.execute(
        "select has_table_privilege(%s, %s, 'select')", (role, f"public.{relation}")
    ).fetchone() == (False,)


def test_agent_runs_has_no_policies(admin_conn):
    assert admin_conn.execute(
        "select count(*) from pg_policies where schemaname = 'public' and tablename = 'agent_runs'"
    ).fetchone() == (0,)


def test_cost_view_runs_with_callers_permissions(admin_conn):
    options = admin_conn.execute(
        "select reloptions from pg_class where oid = 'public.daily_llm_cost'::regclass"
    ).fetchone()[0]
    assert "security_invoker=true" in options


# --- Behaviour (rolled back) ---

def expect_rejected(conn, error, sql, params=()):
    with pytest.raises(error):
        with conn.transaction():
            conn.execute(sql, params)


def conversation(conn, uid):
    return conn.execute(
        "insert into public.conversations (user_id) values (%s) returning id", (uid,)
    ).fetchone()[0]


MESSAGE_INSERT = "insert into public.messages (conversation_id, user_id, role, content) values (%s, %s, %s, %s)"
RUN_INSERT = """
    insert into public.agent_runs (user_id, flow, node, model, input_tokens, output_tokens, cost_usd, latency_ms, status)
    values (%s, 'chat', %s, 'test-model', %s, %s, %s, %s, %s)
"""


def test_message_cannot_belong_to_another_user(scratch_user, add_user):
    conn, uid = scratch_user
    other = add_user(conn)
    conv = conversation(conn, uid)
    conn.execute(MESSAGE_INSERT, (conv, uid, "user", "Had 2 rotis for lunch"))
    expect_rejected(conn, psycopg.errors.ForeignKeyViolation, MESSAGE_INSERT, (conv, other, "user", "hi"))


def test_message_role_and_length_are_checked(scratch_user):
    conn, uid = scratch_user
    conv = conversation(conn, uid)
    expect_rejected(conn, psycopg.errors.CheckViolation, MESSAGE_INSERT, (conv, uid, "system", "x"))
    expect_rejected(conn, psycopg.errors.CheckViolation, MESSAGE_INSERT, (conv, uid, "user", ""))


def test_deleting_an_account_keeps_cost_numbers_but_drops_the_link(scratch_user):
    conn, uid = scratch_user
    conn.execute(RUN_INSERT, (uid, "router", 300, 40, Decimal("0.000123"), 850, "ok"))
    conn.execute("delete from auth.users where id = %s", (uid,))  # cascades to profiles
    assert conn.execute(
        "select user_id, cost_usd from public.agent_runs where model = 'test-model'"
    ).fetchall() == [(None, Decimal("0.000123"))]


def test_daily_cost_view_adds_up_runs(scratch_user):
    conn, uid = scratch_user
    conn.execute(RUN_INSERT, (uid, "router", 300, 40, Decimal("0.000100"), 800, "ok"))
    conn.execute(RUN_INSERT, (uid, "nutrition", 1200, 150, Decimal("0.000400"), 1600, "ok"))
    conn.execute(RUN_INSERT, (uid, "nutrition", 0, 0, Decimal("0"), 50, "rate_limited"))
    row = conn.execute(
        "select runs, failed_runs, input_tokens, output_tokens, cost_usd, avg_latency_ms"
        " from public.daily_llm_cost where model = 'test-model'"
    ).fetchone()
    # 3 runs, 1 not ok; 1500 in / 190 out; $0.0005; avg latency (800 + 1600 + 50) / 3 = 816.7 -> 817
    assert row == (3, 1, 1500, 190, Decimal("0.000500"), 817)


def test_one_usage_counter_per_user_per_day(scratch_user):
    conn, uid = scratch_user
    insert = "insert into public.usage_counters (user_id, day, message_count) values (%s, '2026-11-05', %s)"
    conn.execute(insert, (uid, 1))
    expect_rejected(conn, psycopg.errors.UniqueViolation, insert, (uid, 2))


# --- Acting as a signed-in user (D-025) ---

def test_user_reads_own_messages_only_and_cannot_see_costs(scratch_user, add_user, act_as):
    conn, uid = scratch_user
    other = add_user(conn)
    my_conv = conversation(conn, uid)
    conn.execute(MESSAGE_INSERT, (my_conv, uid, "user", "mine"))
    conn.execute(MESSAGE_INSERT, (conversation(conn, other), other, "user", "theirs"))
    conn.execute(RUN_INSERT, (uid, "router", 300, 40, Decimal("0.0001"), 800, "ok"))

    act_as(conn, uid)
    assert conn.execute("select content from public.messages").fetchall() == [("mine",)]
    expect_rejected(conn, psycopg.errors.InsufficientPrivilege, "select * from public.agent_runs")
    expect_rejected(conn, psycopg.errors.InsufficientPrivilege, "select * from public.daily_llm_cost")
    # Messages are server-written: even in their own conversation, users can't insert directly.
    expect_rejected(conn, psycopg.errors.InsufficientPrivilege, MESSAGE_INSERT, (my_conv, uid, "user", "x"))
