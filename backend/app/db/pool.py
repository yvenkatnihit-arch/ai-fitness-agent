"""One shared connection pool, created on first use (so tests that never touch the DB never connect)."""

import logging
import threading

from psycopg_pool import ConnectionPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Small on purpose: the free Supabase session pooler allows only a few connections per project.
MIN_SIZE = 1
MAX_SIZE = 5
CONNECT_TIMEOUT_S = 10
CHECKOUT_TIMEOUT_S = 10  # how long a request waits for a free connection before failing

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = ConnectionPool(
                conninfo=get_settings().database_url.get_secret_value(),
                min_size=MIN_SIZE,
                max_size=MAX_SIZE,
                timeout=CHECKOUT_TIMEOUT_S,
                kwargs={"connect_timeout": CONNECT_TIMEOUT_S},
                open=False,
            )
            _pool.open(wait=False)  # don't block startup if the DB is briefly unreachable
        return _pool


def close_pool() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def ping() -> bool:
    """True if the database answers a trivial query. Never raises (used by /ready)."""
    try:
        with get_pool().connection(timeout=5) as conn:
            conn.execute("select 1")
        return True
    except Exception:  # noqa: BLE001 - any failure means "not ready"
        logger.warning("database ping failed", exc_info=True)
        return False
