"""Write one agent_runs row per LLM call (tokens, cost, latency). Never breaks the caller."""

import logging
from uuid import UUID

from app.db.transactions import admin_transaction

logger = logging.getLogger(__name__)


def record_run(
    *, user_id: UUID | None, flow: str, node: str, model: str, input_tokens: int, output_tokens: int,
    cached_tokens: int, cost_usd: float, latency_ms: int, status: str, error_code: str | None = None,
) -> None:
    """Logging a run must never fail a user's request, so any database problem is only logged."""
    try:
        with admin_transaction("log agent run") as conn:
            conn.execute(
                "insert into public.agent_runs (user_id, flow, node, model, input_tokens, output_tokens,"
                " cached_tokens, cost_usd, latency_ms, status, error_code)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, flow, node, model, input_tokens, output_tokens, cached_tokens,
                 round(cost_usd, 6), latency_ms, status, error_code),
            )
    except Exception:  # noqa: BLE001 - see docstring
        logger.exception("could not write agent_runs row (flow=%s node=%s)", flow, node)
