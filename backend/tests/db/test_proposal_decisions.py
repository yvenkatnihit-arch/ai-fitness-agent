"""Approving and rejecting proposals against the real database (the model is switched off: code picks exercises)."""

import uuid

import pytest
from psycopg.types.json import Jsonb

from app.db import admin_transaction
from app.llm.client import LLMBusy
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def model_is_down(monkeypatch):
    def down(user_id):
        def ask(prompt):
            raise LLMBusy()
        return ask
    monkeypatch.setattr("app.workflows.pick_exercises._default_ask", down)


@pytest.fixture
def proposal(client):
    onboard(client)
    client.put("/splits/choice", json={"split_key": "full_body_3"})
    return client.post("/plans/workout/generate").json()


def q(sql, *args):
    with admin_transaction("test: read") as conn:
        return conn.execute(sql, args).fetchall()


def plan_rows(user_id):
    return q("select status, version, week_start from public.workout_plans where user_id = %s order by created_at", user_id)


def test_approve_makes_the_proposal_the_active_plan(client, users, proposal):
    assert plan_rows(users[0]) == []                          # generating alone creates no plan
    response = client.post(f"/plans/proposals/{proposal['id']}/approve")
    assert response.status_code == 200 and response.json()["status"] == "approved"

    [(status, version, week_start)] = plan_rows(users[0])
    assert (status, version) == ("active", 1) and week_start.weekday() == 0
    days = q("select day_of_week, focus, is_rest from public.workout_plan_days where user_id = %s order by day_of_week", users[0])
    assert [d[0] for d in days] == [1, 2, 3, 4, 5, 6, 7]
    assert [d[2] for d in days] == [False, True, False, True, False, True, True]
    stored = q("""select d.day_of_week, e.position, x.key, e.sets, e.reps_min, e.reps_max, e.rest_sec, e.target_load_note
                  from public.workout_plan_exercises e join public.workout_plan_days d on d.id = e.plan_day_id
                  join public.exercises x on x.id = e.exercise_id
                  where e.user_id = %s order by d.day_of_week, e.position""", users[0])
    wanted = [(d["day_of_week"], e["position"], e["exercise_key"], e["sets"], e["reps_min"], e["reps_max"], e["rest_sec"], e["note"])
              for d in proposal["payload"]["days"] for e in d["exercises"]]
    assert stored == wanted                                   # exactly what the user was shown
    [(decided,)] = q("select decided_at is not null from public.plan_proposals where id = %s", uuid.UUID(proposal["id"]))
    assert decided


def test_approving_twice_does_not_make_a_second_plan(client, users, proposal):
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200
    again = client.post(f"/plans/proposals/{proposal['id']}/approve")
    assert again.status_code == 409 and "already been decided" in again.json()["detail"]
    assert len(plan_rows(users[0])) == 1


def test_a_new_approval_archives_the_old_plan_so_exactly_one_is_active(client, users, proposal):
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    second = client.post("/plans/workout/generate").json()
    assert second["id"] != proposal["id"]
    assert client.post(f"/plans/proposals/{second['id']}/approve").status_code == 200
    rows = plan_rows(users[0])
    assert sorted(r[0] for r in rows) == ["active", "archived"]
    assert [(r[0], r[1]) for r in rows] == [("archived", 1), ("active", 2)]      # same Monday, so the new one is version 2
    [(active,)] = q("select count(*) from public.workout_plans where user_id = %s and status = 'active'", users[0])
    assert active == 1


def test_reject_changes_nothing_else(client, users, proposal):
    response = client.post(f"/plans/proposals/{proposal['id']}/reject")
    assert response.status_code == 200 and response.json()["status"] == "rejected"
    assert plan_rows(users[0]) == []
    assert client.get("/plans/proposals/pending").json() == {"proposals": []}
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 409     # a rejected plan cannot be approved


def test_nobody_can_decide_someone_elses_proposal(client, users, proposal):
    client.session.user_id = users[1]
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 404
    assert client.post(f"/plans/proposals/{proposal['id']}/reject").status_code == 404
    assert plan_rows(users[0]) == [] and plan_rows(users[1]) == []
    [(status,)] = q("select status from public.plan_proposals where id = %s", uuid.UUID(proposal["id"]))
    assert status == "pending"                                # untouched


def test_an_unknown_id_is_a_404(client):
    onboard(client)
    assert client.post(f"/plans/proposals/{uuid.uuid4()}/approve").status_code == 404
    assert client.post("/plans/proposals/not-a-uuid/approve").status_code == 422


def test_a_tampered_plan_is_refused_and_nothing_is_written(client, users, proposal):
    with admin_transaction("test: tamper with the stored plan") as conn:
        conn.execute(
            "update public.plan_proposals set payload = jsonb_set(payload, '{days,0,exercises,0,exercise_key}', '\"invented_lift\"')"
            " where id = %s", (uuid.UUID(proposal["id"]),))
    response = client.post(f"/plans/proposals/{proposal['id']}/approve")
    assert response.status_code == 422 and "safety checks" in response.json()["detail"]
    assert plan_rows(users[0]) == []
    [(status,)] = q("select status from public.plan_proposals where id = %s", uuid.UUID(proposal["id"]))
    assert status == "pending"


def test_other_kinds_of_proposal_are_refused_until_their_apply_code_exists(client, users):
    onboard(client)
    with admin_transaction("test: insert a meal proposal") as conn:
        pid = conn.execute(
            "insert into public.plan_proposals (user_id, type, source, summary, payload) values (%s, 'meal_change', 'chat', 'x', %s) returning id",
            (users[0], Jsonb({"kind": "meal_change"}))).fetchone()[0]
    response = client.post(f"/plans/proposals/{pid}/approve")
    assert response.status_code == 422 and "cannot be approved yet" in response.json()["detail"]
    [(status,)] = q("select status from public.plan_proposals where id = %s", pid)
    assert status == "pending"                                # NOT silently marked approved


def test_a_plan_whose_monday_has_passed_starts_on_the_coming_monday(client, users, proposal):
    with admin_transaction("test: make the planned Monday old") as conn:
        conn.execute("update public.plan_proposals set payload = jsonb_set(payload, '{week_start}', '\"2026-01-05\"') where id = %s",
                     (uuid.UUID(proposal["id"]),))
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200
    [(_, _, week_start)] = plan_rows(users[0])
    from app.core.time import india_today
    assert week_start.weekday() == 0 and week_start >= india_today()


def test_the_active_plan_is_readable_only_after_approval_and_only_by_its_owner(client, users, proposal):
    assert client.get("/plans/workout/active").status_code == 404           # a proposal is not a plan
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    body = client.get("/plans/workout/active").json()
    assert body["version"] == 1 and [d["day_of_week"] for d in body["days"]] == [1, 2, 3, 4, 5, 6, 7]
    shown = [(e["exercise_key"], e["sets"]) for d in proposal["payload"]["days"] for e in d["exercises"]]
    assert [(e["exercise_key"], e["sets"]) for d in body["days"] for e in d["exercises"]] == shown
    assert all(e["form_cues"] and e["name"] for d in body["days"] for e in d["exercises"])
    client.session.user_id = users[1]
    assert client.get("/plans/workout/active").status_code == 404           # not visible to anyone else


def test_an_approved_plan_that_is_replaced_is_no_longer_the_active_one(client, users, proposal):
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    first_id = client.get("/plans/workout/active").json()["id"]
    second = client.post("/plans/workout/generate").json()
    client.post(f"/plans/proposals/{second['id']}/approve")
    assert client.get("/plans/workout/active").json()["id"] != first_id
