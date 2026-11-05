"""Transactions that decide WHO the database thinks is asking (D-025).

user_transaction(user_id): queries run as Supabase's `authenticated` role with the user's id
in the JWT claims, so every RLS policy applies exactly as if the user made the query.
`set local` / `set_config(..., true)` only last until the transaction ends, so a pooled
connection never carries one user's identity into the next request.

admin_transaction(reason): the admin connection, which BYPASSES RLS. Only for system jobs
(migrations, plan generation, applying approved proposals, logging agent_runs). Always
pass a reason; it is logged so admin access is easy to audit.
"""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from psycopg import Connection

from app.db.pool import get_pool

logger = logging.getLogger(__name__)


@contextmanager
def user_transaction(user_id: UUID) -> Iterator[Connection]:
    """Run queries as this signed-in user, under RLS. Commits on success, rolls back on error."""
    if not isinstance(user_id, UUID):
        raise TypeError("user_id must be a UUID taken from a verified JWT, never from request data")
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute("set local role authenticated")
            conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
            yield conn


@contextmanager
def admin_transaction(reason: str) -> Iterator[Connection]:
    """Run queries as the admin (no RLS). For system jobs only; `reason` is logged."""
    if not reason or not reason.strip():
        raise ValueError("admin_transaction needs a reason, e.g. 'apply approved proposal'")
    logger.info("admin transaction: %s", reason)
    with get_pool().connection() as conn:
        with conn.transaction():
            yield conn
