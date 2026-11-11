"""Step 8.6 (D-112): the weight log against the real database."""

from datetime import timedelta

import pytest

from app.core.time import india_today
from app.db import admin_transaction
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


def ago(n):
    return (india_today() - timedelta(days=n)).isoformat()


def stored(user):
    with admin_transaction("test: weights") as conn:
        return conn.execute("select measured_on, weight_kg from public.body_weight_entries where user_id = %s order by measured_on", (user,)).fetchall()


def test_a_new_user_starts_with_the_weight_from_onboarding_and_the_distance_to_their_target(client, users):
    onboard(client)                                                                               # 58 kg, target 54 kg (fat loss)
    body = client.get("/weight").json()
    assert body["numbers_hidden"] is False and [e["weight_kg"] for e in body["entries"]] == [58.0]
    assert (body["latest_kg"], body["start_weight_kg"], body["target_weight_kg"]) == (58.0, 58.0, 54.0)
    assert body["kg_to_target"] == -4.0 and body["change_since_start_kg"] == 0.0 and body["percent_to_target"] == 0 and body["weekly_change_kg"] is None


def test_a_weigh_in_moves_the_trend_and_a_second_one_the_same_day_replaces_the_first(client, users):
    onboard(client)
    assert client.post("/weight", json={"weight_kg": 57.5}).status_code == 200
    body = client.post("/weight", json={"weight_kg": 57.0}).json()
    assert [e["weight_kg"] for e in body["entries"]] == [57.0]                                    # one entry per day: today's was replaced
    assert body["change_since_start_kg"] == -1.0 and body["kg_to_target"] == -3.0 and body["percent_to_target"] == 25


def test_history_gives_a_weekly_rate_and_a_chart_ready_list_in_date_order(client, users):
    onboard(client)
    client.post("/weight", json={"weight_kg": 59.5, "measured_on": ago(10)})
    body = client.post("/weight", json={"weight_kg": 57.0}).json()
    assert [e["date"] for e in body["entries"]] == sorted(e["date"] for e in body["entries"]) and len(body["entries"]) == 2
    assert body["weekly_change_kg"] == -1.75                                                      # (57.0 - 59.5) / 10 days * 7


def test_logging_a_weight_does_not_change_the_daily_targets_but_does_move_the_goal_date_forecast(client, users):
    onboard(client)
    targets = client.get("/targets/current").json()
    before = client.get("/targets/forecast").json()
    client.post("/weight", json={"weight_kg": 56.0})
    assert client.get("/targets/current").json() == targets                                       # targets change only when weight is edited in Settings
    after = client.get("/targets/forecast").json()
    assert before["current_weight_kg"] == 58.0 and after["current_weight_kg"] == 56.0             # the forecast starts from the latest weight


@pytest.mark.parametrize("body", [{"weight_kg": 20}, {"weight_kg": 400}, {"weight_kg": "heavy"}, {}, {"weight_kg": 60, "user_id": "x"}])
def test_a_silly_weight_or_extra_field_is_refused_and_nothing_is_saved(client, users, body):
    onboard(client)
    assert client.post("/weight", json=body).status_code == 422
    assert len(stored(users[0])) == 1                                                             # only the onboarding weight


def test_future_and_too_old_dates_are_refused_with_a_clear_message(client, users):
    onboard(client)
    future = client.post("/weight", json={"weight_kg": 57, "measured_on": (india_today() + timedelta(days=1)).isoformat()})
    old = client.post("/weight", json={"weight_kg": 57, "measured_on": ago(61)})
    assert future.status_code == 422 and "future" in future.json()["detail"]
    assert old.status_code == 422 and "last 60 days" in old.json()["detail"]
    assert len(stored(users[0])) == 1


def test_a_mistaken_weigh_in_can_be_deleted_and_a_missing_one_is_a_404(client, users):
    onboard(client)
    client.post("/weight", json={"weight_kg": 59.0, "measured_on": ago(3)})
    assert client.delete(f"/weight/{ago(3)}").status_code == 204
    assert client.delete(f"/weight/{ago(3)}").status_code == 404
    assert len(stored(users[0])) == 1


def test_a_user_who_must_not_see_numbers_sees_no_weights_and_cannot_log_or_delete_any(client, users):
    onboard(client, eating_disorder_history=True)
    body = client.get("/weight").json()
    assert body["numbers_hidden"] is True and body["entries"] == [] and body["latest_kg"] is None and body["target_weight_kg"] is None
    refused = client.post("/weight", json={"weight_kg": 57.0})
    assert refused.status_code == 403 and "weights are not tracked" in refused.json()["detail"]
    assert client.delete(f"/weight/{india_today().isoformat()}").status_code == 403
    assert len(stored(users[0])) == 1                                                             # nothing was added to what onboarding stored


def test_nobody_sees_or_changes_anyone_elses_weights(client, users):
    onboard(client)
    client.post("/weight", json={"weight_kg": 57.0})
    client.session.user_id = users[1]
    assert client.get("/weight").json()["entries"] == []
    assert client.delete(f"/weight/{india_today().isoformat()}").status_code == 404                # not theirs: reads as "none"
    client.session.user_id = users[0]
    assert [e["weight_kg"] for e in client.get("/weight").json()["entries"]] == [57.0]


def test_the_weight_log_needs_a_login(users):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anonymous:
        assert anonymous.get("/weight").status_code in (401, 403)
        assert anonymous.post("/weight", json={"weight_kg": 57}).status_code in (401, 403)
        assert anonymous.delete(f"/weight/{india_today().isoformat()}").status_code in (401, 403)
