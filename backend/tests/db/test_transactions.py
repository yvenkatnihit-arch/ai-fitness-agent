"""The real backend helpers against Supabase. These COMMIT, so each test cleans up its own users."""

import uuid

import psycopg.errors
import pytest

from app.db import admin_transaction, close_pool, ping, user_transaction

pytestmark = pytest.mark.db

WEIGHT_INSERT = "insert into public.body_weight_entries (user_id, measured_on, weight_kg) values (%s, %s, %s)"


@pytest.fixture(scope="module", autouse=True)
def pool_lifecycle():
    yield
    close_pool()


@pytest.fixture
def two_users():
    """Two committed throwaway users (auth + profile). Deleted afterwards; deletes cascade."""
    ids = [uuid.uuid4(), uuid.uuid4()]
    with admin_transaction("test setup: create scratch users") as conn:
        for uid in ids:
            conn.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"scratch-{uid}@example.test"))
            conn.execute("insert into public.profiles (id) values (%s)", (uid,))
    try:
        yield ids
    finally:
        with admin_transaction("test cleanup: delete scratch users") as conn:
            conn.execute("delete from auth.users where id = any(%s)", (ids,))


def test_ping():
    assert ping() is True


def test_user_transaction_applies_rls(two_users):
    alice, bob = two_users
    with user_transaction(alice) as conn:
        conn.execute(WEIGHT_INSERT, (alice, "2026-11-05", 62.5))

    with user_transaction(alice) as conn:
        assert conn.execute("select count(*) from public.body_weight_entries").fetchone() == (1,)
    with user_transaction(bob) as conn:
        assert conn.execute("select count(*) from public.body_weight_entries").fetchone() == (0,)


def test_user_cannot_write_for_someone_else(two_users):
    alice, bob = two_users
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with user_transaction(alice) as conn:
            conn.execute(WEIGHT_INSERT, (bob, "2026-11-05", 70))


def test_error_rolls_back_the_whole_transaction(two_users):
    alice, _ = two_users
    with pytest.raises(RuntimeError):
        with user_transaction(alice) as conn:
            conn.execute(WEIGHT_INSERT, (alice, "2026-11-05", 62.5))
            raise RuntimeError("something failed after the insert")
    with user_transaction(alice) as conn:
        assert conn.execute("select count(*) from public.body_weight_entries").fetchone() == (0,)


def test_identity_never_leaks_into_the_next_use_of_a_pooled_connection(two_users):
    alice, _ = two_users
    with user_transaction(alice) as conn:
        assert conn.execute("select current_user, auth.uid()").fetchone() == ("authenticated", alice)

    # The same pool hands out connections again. Run enough to reuse every connection.
    for _ in range(10):
        with admin_transaction("test: check connection state after a user transaction") as conn:
            role, uid = conn.execute("select current_user, auth.uid()").fetchone()
            assert role == "postgres"
            assert uid is None  # no leftover JWT claims


def test_admin_transaction_bypasses_rls(two_users):
    alice, bob = two_users
    with admin_transaction("test: system job writing for a user") as conn:
        conn.execute(WEIGHT_INSERT, (alice, "2026-11-05", 62.5))
        conn.execute(WEIGHT_INSERT, (bob, "2026-11-05", 80.0))
        assert conn.execute(
            "select count(*) from public.body_weight_entries where user_id = any(%s)", (two_users,)
        ).fetchone() == (2,)
