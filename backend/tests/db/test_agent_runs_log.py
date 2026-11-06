"""record_run writes a real agent_runs row (own rows are removed again by exact content)."""

import pytest

from app.db.transactions import admin_transaction
from app.llm.runs import record_run

pytestmark = pytest.mark.db


def test_record_run_inserts_a_row():
    marker = "pytest-record-run"
    try:
        record_run(user_id=None, flow="plan_generation", node=marker, model="gemini-2.5-flash", input_tokens=10,
                   output_tokens=5, cached_tokens=2, cost_usd=0.000123, latency_ms=250, status="ok")
        with admin_transaction("test: read agent_runs") as conn:
            row = conn.execute(
                "select input_tokens, output_tokens, cached_tokens, cost_usd, latency_ms, status"
                " from public.agent_runs where node = %s", (marker,)
            ).fetchone()
        assert (row[0], row[1], row[2], row[4], row[5]) == (10, 5, 2, 250, "ok")
        assert float(row[3]) == pytest.approx(0.000123)   # numeric comes back as Decimal
    finally:
        with admin_transaction("test: remove own agent_runs row") as conn:
            conn.execute("delete from public.agent_runs where node = %s", (marker,))


def test_a_bad_row_is_swallowed_not_raised():
    record_run(user_id=None, flow="not-a-flow", node="x", model="m", input_tokens=0, output_tokens=0,
               cached_tokens=0, cost_usd=0, latency_ms=0, status="ok")   # violates the flow check; must not raise
