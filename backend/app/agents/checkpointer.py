"""LangGraph checkpointer on Supabase Postgres (D-012).

The checkpointer saves a graph's state after every step, so a conversation survives a
server restart. Its tables live in the private `langgraph` schema, away from our RLS tables.

Connection rules LangGraph needs (checked by tests/db/test_checkpointer.py):
- autocommit=True and dict rows.
- The Session pooler (port 5432), not the Transaction pooler: the connection must stay
  ours for the whole session, because we set search_path on it and psycopg uses
  prepared statements.
Phase 7 will swap this single connection for an async pool with the same settings.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from app.core.config import get_settings

SCHEMA = "langgraph"


@contextmanager
def checkpointer() -> Iterator[PostgresSaver]:
    conn = psycopg.connect(
        get_settings().database_url.get_secret_value(),
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=10,
    )
    try:
        conn.execute(f"set search_path to {SCHEMA}")  # LangGraph's unqualified table names land here
        yield PostgresSaver(conn)
    finally:
        conn.close()


def setup_checkpointer_tables() -> None:
    """Create or upgrade LangGraph's tables. Safe to run repeatedly (migrate.py runs it)."""
    with checkpointer() as saver:
        saver.setup()
