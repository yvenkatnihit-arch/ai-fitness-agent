"""The person's OWN AI usage and the published quality results (Step 8.7, D-113). Reads only; no model is called.

`agent_runs` has no user policy on purpose (cost data is backend-only), so this reads it on the admin connection with the caller's id
in the query, and only their own rows can come back. Evals are not run here: the numbers are the last recorded runs, with their date."""

import json
from pathlib import Path
from uuid import UUID

from app.db import admin_transaction
from app.schemas.insights import EvalsOut, InsightsOut, RULES, UsageDay, UsageOut, UsageStep, UsageTotals

PUBLISHED = Path(__file__).resolve().parents[2] / "evals" / "published_results.json"
USER_FLOWS = ("chat", "plan_generation", "summary")     # eval runs and other system flows are not "your" usage
STEP_NAMES = {"router": "router", "composer": "composer", "chat_summary": "chat summary", "nutrition": "nutrition specialist",
              "my_plan": "my plan specialist", "exercises": "exercise specialist", "meal_logger": "meal logger"}


def published_results() -> EvalsOut:
    return EvalsOut(**json.loads(PUBLISHED.read_text(encoding="utf-8")))


def usage_for(user_id: UUID, days: int = 14) -> UsageOut:
    with admin_transaction("show a user their own AI usage") as conn:
        total = conn.execute(
            """select count(*), coalesce(sum(input_tokens), 0), coalesce(sum(output_tokens), 0), coalesce(sum(cost_usd), 0),
                      coalesce(avg(latency_ms), 0), count(*) filter (where status <> 'ok')
               from public.agent_runs
               where user_id = %s and flow = any(%s) and created_at > now() - make_interval(days => %s)""", (user_id, list(USER_FLOWS), days)).fetchone()
        per_day = conn.execute(
            """select (created_at at time zone 'Asia/Kolkata')::date as day, count(*), coalesce(sum(cost_usd), 0)
               from public.agent_runs where user_id = %s and flow = any(%s) and created_at > now() - make_interval(days => %s)
               group by 1 order by 1""", (user_id, list(USER_FLOWS), days)).fetchall()
        per_step = conn.execute(
            """select node, count(*), coalesce(avg(latency_ms), 0), coalesce(sum(cost_usd), 0)
               from public.agent_runs where user_id = %s and flow = any(%s) and created_at > now() - make_interval(days => %s)
               group by node order by count(*) desc, node""", (user_id, list(USER_FLOWS), days)).fetchall()
    return UsageOut(
        days=days,
        totals=UsageTotals(calls=total[0], input_tokens=int(total[1]), output_tokens=int(total[2]), cost_usd=round(float(total[3]), 4),
                           avg_latency_ms=round(float(total[4])), failed_calls=total[5]),
        per_day=[UsageDay(day=r[0], calls=r[1], cost_usd=round(float(r[2]), 4)) for r in per_day],
        per_step=[UsageStep(step=STEP_NAMES.get(r[0], r[0].replace("_", " ")), calls=r[1], avg_latency_ms=round(float(r[2])), cost_usd=round(float(r[3]), 4))
                  for r in per_step])


def insights_for(user_id: UUID, days: int = 14) -> InsightsOut:
    return InsightsOut(usage=usage_for(user_id, days), quality=published_results(), rules=RULES)
