"""Step 8.7 (D-113): the AI usage page's data against the real database."""

from decimal import Decimal

import pytest

from app.db import admin_transaction
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db

RUN = ("insert into public.agent_runs (user_id, flow, node, model, input_tokens, output_tokens, cost_usd, latency_ms, status) "
       "values (%s, %s, %s, 'test-model', %s, %s, %s, %s, %s)")


def log(user, flow, node, tin, tout, cost, ms, status="ok"):
    with admin_transaction("test: log a run") as conn:
        conn.execute(RUN, (user, flow, node, tin, tout, Decimal(str(cost)), ms, status))


def test_a_user_with_no_ai_calls_sees_zeros_and_still_gets_the_quality_results_and_rules(client, users):
    onboard(client)
    body = client.get("/insights/ai").json()
    assert body["usage"]["totals"] == {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "avg_latency_ms": 0, "failed_calls": 0}
    assert body["usage"]["per_day"] == [] and body["usage"]["per_step"] == []
    assert len(body["quality"]["evals"]) >= 5 and len(body["rules"]) >= 6


def test_usage_adds_up_the_users_own_calls_by_total_day_and_step(client, users):
    onboard(client)
    log(users[0], "chat", "router", 400, 20, 0.0002, 800)
    log(users[0], "chat", "router", 400, 20, 0.0002, 1200)
    log(users[0], "chat", "nutrition", 1000, 100, 0.001, 2000)
    log(users[0], "chat", "nutrition", 0, 0, 0, 100, status="rate_limited")
    body = client.get("/insights/ai").json()["usage"]
    assert body["totals"] == {"calls": 4, "input_tokens": 1800, "output_tokens": 140, "cost_usd": 0.0014, "avg_latency_ms": 1025, "failed_calls": 1}
    assert [(d["calls"], d["cost_usd"]) for d in body["per_day"]] == [(4, 0.0014)]
    steps = {s["step"]: s for s in body["per_step"]}
    assert steps["router"]["calls"] == 2 and steps["router"]["avg_latency_ms"] == 1000 and steps["nutrition specialist"]["calls"] == 2
    assert [s["calls"] for s in body["per_step"]] == sorted((s["calls"] for s in body["per_step"]), reverse=True)


def test_other_users_calls_and_eval_or_system_flows_are_never_counted(client, users):
    onboard(client)
    log(users[0], "chat", "router", 100, 10, 0.0001, 500)
    with admin_transaction("test: a second user with a profile") as conn:
        conn.execute("insert into public.profiles (id) values (%s) on conflict do nothing", (users[1],))
    log(users[1], "chat", "router", 9000, 900, 0.5, 9000)                                    # someone else's usage
    log(users[0], "eval", "router", 9000, 900, 0.5, 9000)                                    # a quality-eval call, not the user's usage
    body = client.get("/insights/ai").json()["usage"]
    assert body["totals"]["calls"] == 1 and body["totals"]["cost_usd"] == 0.0001


def test_the_window_is_validated_and_old_calls_fall_out_of_it(client, users):
    onboard(client)
    log(users[0], "chat", "router", 100, 10, 0.0001, 500)
    with admin_transaction("test: age the call") as conn:
        conn.execute("update public.agent_runs set created_at = now() - interval '30 days' where user_id = %s", (users[0],))
    assert client.get("/insights/ai").json()["usage"]["totals"]["calls"] == 0                 # default 14 days
    assert client.get("/insights/ai", params={"days": 60}).json()["usage"]["totals"]["calls"] == 1
    assert client.get("/insights/ai", params={"days": 0}).status_code == 422 and client.get("/insights/ai", params={"days": 500}).status_code == 422


def test_the_page_needs_a_login(users):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anonymous:
        assert anonymous.get("/insights/ai").status_code in (401, 403)
