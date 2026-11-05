"""Print LLM cost per day and model from the daily_llm_cost view (D-013).

Run from backend/:
    uv run python scripts/daily_cost.py           # last 14 days
    uv run python scripts/daily_cost.py 30        # last 30 days
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg  # noqa: E402

from app.core.config import get_settings  # noqa: E402

QUERY = """
    select day, model, runs, failed_runs, input_tokens, output_tokens, cost_usd, avg_latency_ms, p95_latency_ms
    from public.daily_llm_cost
    where day > (now() at time zone 'Asia/Kolkata')::date - %s
    order by day desc, cost_usd desc
"""


def main() -> int:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    with psycopg.connect(get_settings().database_url.get_secret_value(), connect_timeout=10) as conn:
        rows = conn.execute(QUERY, (days,)).fetchall()

    if not rows:
        print(f"No LLM calls in the last {days} days.")
        return 0

    print(f"{'day':<11} {'model':<28} {'runs':>5} {'fail':>4} {'in tok':>9} {'out tok':>8} "
          f"{'cost $':>9} {'avg ms':>7} {'p95 ms':>7}")
    total = 0
    for day, model, runs, failed, tin, tout, cost, avg_ms, p95_ms in rows:
        total += cost
        print(f"{day!s:<11} {model:<28} {runs:>5} {failed:>4} {tin:>9} {tout:>8} "
              f"{cost:>9.4f} {avg_ms:>7} {p95_ms:>7}")
    print(f"\nTotal for the last {days} days: ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
