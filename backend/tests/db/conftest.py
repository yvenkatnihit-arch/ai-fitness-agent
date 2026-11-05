import json
import uuid

import psycopg
import pytest

from app.core.config import get_settings


def _url() -> str:
    return get_settings().database_url.get_secret_value()


@pytest.fixture(scope="session")
def admin_conn():
    """Admin connection for checking the schema (catalog queries only)."""
    with psycopg.connect(_url(), connect_timeout=10, autocommit=True) as conn:
        yield conn


@pytest.fixture
def scratch_user():
    """A throwaway user + profile inside one transaction that is ALWAYS rolled back.

    Yields (conn, user_id). Nothing the test writes survives, so these tests leave
    no data behind. Wrap an expected failure in `with conn.transaction():` (a savepoint)
    so the outer transaction stays usable.
    """
    conn = psycopg.connect(_url(), connect_timeout=10)
    user_id = uuid.uuid4()
    try:
        conn.execute(
            "insert into auth.users (id, email) values (%s, %s)",
            (user_id, f"scratch-{user_id}@example.test"),
        )
        conn.execute("insert into public.profiles (id) values (%s)", (user_id,))
        yield conn, user_id
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def add_user():
    """Returns a function that adds another throwaway user to the same transaction."""

    def _add(conn) -> uuid.UUID:
        other = uuid.uuid4()
        conn.execute(
            "insert into auth.users (id, email) values (%s, %s)", (other, f"scratch-{other}@example.test")
        )
        conn.execute("insert into public.profiles (id) values (%s)", (other,))
        return other

    return _add


@pytest.fixture
def act_as():
    """Returns a function that switches the transaction to a signed-in user, as the backend will (D-025)."""

    def _act_as(conn, user_id) -> None:
        conn.execute("set local role authenticated")
        conn.execute(
            "select set_config('request.jwt.claims', %s, true)",
            (json.dumps({"sub": str(user_id), "role": "authenticated"}),),
        )

    return _act_as
