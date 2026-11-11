"""Step 8.5 (D-109): logging a meal by chat against the real database. The model is replaced by a script; the tool, the proposal, the approval
and the meal log are all real."""

import uuid
from datetime import timedelta

import pytest

from app.agents.context import RunContext
from app.agents.log_tools import PROPOSE_MEAL_LOG, LogMealArgs
from app.core.time import india_today
from app.db import admin_transaction
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


def propose(user, slot="lunch", day="today", items=None):
    items = items or [{"food_key": "roti", "quantity": 2, "unit": "piece"}, {"food_key": "sambar", "quantity": 1, "unit": "katori"}]
    return PROPOSE_MEAL_LOG.run(RunContext(user), LogMealArgs(slot=slot, day=day, items=items))


def rows(sql, *args):
    with admin_transaction("test: read") as conn:
        return conn.execute(sql, args).fetchall()


def logged_today(client):
    return client.get("/meals").json()


# ---------- the proposal: nothing is logged ----------

def test_proposing_a_meal_saves_a_pending_proposal_and_logs_nothing(client, users):
    onboard(client)
    out = propose(users[0])
    assert uuid.UUID(out["proposal_id"]) and out["summary"].startswith("Log for lunch today: ")
    assert [w["food"][:4] for w in out["will_log"]] == ["Roti", "Samb"] and out["will_log"][0]["amount"] == "2 piece"
    assert logged_today(client)["meals"] == []                                              # NOTHING is logged yet
    [(kind, source, status)] = rows("select type, source, status from public.plan_proposals where id = %s", out["proposal_id"])
    assert (kind, source, status) == ("meal_log", "chat", "pending")


def test_the_summary_shows_grams_and_calories_worked_out_by_code(client, users):
    onboard(client)
    out = propose(users[0], items=[{"food_key": "roti", "quantity": 2, "unit": "piece"}])
    assert "2 piece" in out["summary"] and "(" in out["summary"] and out["summary"].endswith(" kcal.")
    assert out["will_log"][0]["grams"] > 0


def test_a_user_who_must_not_see_numbers_gets_a_summary_without_calories(client, users):
    onboard(client, eating_disorder_history=True)
    summary = propose(users[0])["summary"]
    assert "kcal" not in summary and "Roti" in summary


@pytest.mark.parametrize("items, fragment", [
    ([{"food_key": "not_a_food", "quantity": 1, "unit": "g"}], "not in our database"),
    ([{"food_key": "roti", "quantity": 1, "unit": "bucket"}], "Available units"),
])
def test_a_bad_food_or_unit_is_reported_back_to_the_model_to_fix_and_nothing_is_saved(client, users, items, fragment):
    onboard(client)
    out = propose(users[0], items=items)
    assert "error" in out and fragment in out["error"]
    assert rows("select count(*) from public.plan_proposals where user_id = %s and type = 'meal_log'", users[0]) == [(0,)]


def test_a_new_proposal_replaces_the_old_pending_one(client, users):
    onboard(client)
    first = propose(users[0])["proposal_id"]
    second = propose(users[0], slot="dinner")["proposal_id"]
    assert dict(rows("select id::text, status from public.plan_proposals where user_id = %s and type = 'meal_log'", users[0])) == {first: "expired", second: "pending"}


def test_the_arguments_cannot_name_a_user_or_use_an_unknown_meal_or_too_many_foods():
    from pydantic import ValidationError
    ok = {"slot": "lunch", "items": [{"food_key": "roti", "quantity": 1, "unit": "piece"}]}
    LogMealArgs(**ok)
    for bad in ({**ok, "user_id": "x"}, {**ok, "slot": "brunch"}, {**ok, "day": "tomorrow"}, {**ok, "items": []},
                {**ok, "items": [{"food_key": "roti", "quantity": 1, "unit": "piece"}] * 21}, {**ok, "items": [{"food_key": "roti", "quantity": 0, "unit": "g"}]},
                {**ok, "items": [{"food_key": "roti", "quantity": 1, "unit": "piece", "kcal": 1}]}):
        with pytest.raises(ValidationError):
            LogMealArgs(**bad)


def test_the_tool_is_a_propose_tool_so_the_harness_pauses_the_chat(client, users):
    assert PROPOSE_MEAL_LOG.scope == "propose"


# ---------- the approval: only now is the meal logged ----------

def test_approving_logs_the_meal_exactly_like_the_form_would(client, users):
    onboard(client)
    out = propose(users[0])
    assert client.post(f"/plans/proposals/{out['proposal_id']}/approve").status_code == 200
    day = logged_today(client)
    [meal] = day["meals"]
    assert meal["slot"] == "lunch" and meal["source"] == "chat" and len(meal["items"]) == 2
    assert [(i["quantity"], i["unit"]) for i in meal["items"]] == [(2.0, "piece"), (1.0, "katori")]
    form = client.post("/meals", json={"slot": "lunch", "items": [
        {"food_id": meal["items"][0]["food_id"], "quantity": 2, "unit": "piece"}, {"food_id": meal["items"][1]["food_id"], "quantity": 1, "unit": "katori"}]}).json()
    assert meal["totals"] == form["totals"]                                                # the same numbers as logging on the form


def test_rejecting_logs_nothing(client, users):
    onboard(client)
    out = propose(users[0])
    assert client.post(f"/plans/proposals/{out['proposal_id']}/reject").status_code == 200
    assert logged_today(client)["meals"] == []


def test_approving_twice_logs_once(client, users):
    onboard(client)
    pid = propose(users[0])["proposal_id"]
    assert client.post(f"/plans/proposals/{pid}/approve").status_code == 200
    assert client.post(f"/plans/proposals/{pid}/approve").status_code == 409
    assert len(logged_today(client)["meals"]) == 1


def test_yesterday_is_logged_on_yesterday(client, users):
    onboard(client)
    pid = propose(users[0], day="yesterday")["proposal_id"]
    client.post(f"/plans/proposals/{pid}/approve")
    assert client.get("/meals", params={"day": (india_today() - timedelta(days=1)).isoformat()}).json()["meals"][0]["source"] == "chat"
    assert logged_today(client)["meals"] == []


def test_a_proposal_whose_food_was_removed_is_refused_at_approval_and_logs_nothing(client, users):
    onboard(client)
    pid = propose(users[0])["proposal_id"]
    with admin_transaction("test: tamper with the stored proposal") as conn:                # what the stored payload says is re-checked, not trusted
        conn.execute("""update public.plan_proposals set payload = jsonb_set(payload, '{items,0,food_key}', '"not_a_food"') where id = %s""", (pid,))
    response = client.post(f"/plans/proposals/{pid}/approve")
    assert response.status_code == 422 and "not in our database" in response.json()["detail"]
    assert logged_today(client)["meals"] == []
    assert rows("select status from public.plan_proposals where id = %s", pid) == [("pending",)]


def test_a_stored_proposal_with_a_date_too_far_back_is_refused(client, users):
    onboard(client)
    pid = propose(users[0])["proposal_id"]
    old = (india_today() - timedelta(days=30)).isoformat()
    with admin_transaction("test: tamper with the date") as conn:
        conn.execute("update public.plan_proposals set payload = jsonb_set(payload, '{logged_on}', to_jsonb(%s::text)) where id = %s", (old, pid))
    assert client.post(f"/plans/proposals/{pid}/approve").status_code == 422
    assert logged_today(client)["meals"] == []


def test_nobody_can_approve_someone_elses_meal_log(client, users):
    onboard(client)
    pid = propose(users[0])["proposal_id"]
    client.session.user_id = users[1]
    assert client.post(f"/plans/proposals/{pid}/approve").status_code == 404
    client.session.user_id = users[0]
    assert logged_today(client)["meals"] == []                                              # still nothing logged, still pending
    assert rows("select status from public.plan_proposals where id = %s", pid) == [("pending",)]
