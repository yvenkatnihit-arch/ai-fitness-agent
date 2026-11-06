"""Generating a workout plan end to end against the real database, with the model switched off.

With the model unavailable the code fallback picks the exercises, so these tests are free and offline from
Gemini but exercise everything else: filters, routine rules, validation, the pending proposal and RLS.
"""

import pytest

from app.calc.workout_plan import validate_payload
from app.db import admin_transaction, user_transaction
from app.db.exercises import list_exercises
from app.llm.client import LLMBusy
from tests.db.test_onboarding_complete import FORMS, client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def model_is_down(monkeypatch):
    def down(user_id):
        def ask(prompt):
            raise LLMBusy()
        return ask
    monkeypatch.setattr("app.workflows.pick_exercises._default_ask", down)


def known_keys(user_id):
    with user_transaction(user_id) as conn:
        return {o.key for o in list_exercises(conn)}


def pending_count(user_id):
    with admin_transaction("test: count pending proposals") as conn:
        return conn.execute(
            "select count(*) from public.plan_proposals where user_id = %s and status = 'pending'", (user_id,)
        ).fetchone()[0]


def test_nothing_to_generate_before_onboarding(client):
    response = client.post("/plans/workout/generate")
    assert response.status_code == 409 and "finish onboarding" in response.json()["detail"]


def test_a_split_must_be_chosen_first(client):
    onboard(client)
    response = client.post("/plans/workout/generate")
    assert response.status_code == 409 and "choose a workout split" in response.json()["detail"]
    assert pending_count(client.session.user_id) == 0


def test_generates_a_valid_pending_proposal_and_never_activates_a_plan(client, users):
    onboard(client)
    client.put("/splits/choice", json={"split_key": "full_body_3"})
    response = client.post("/plans/workout/generate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "workout_change" and body["source"] == "plan_generation" and body["status"] == "pending"
    assert body["summary"].startswith("Full body, 3 days a week: Mon Full body A, Wed Full body B, Fri Full body C")
    payload = body["payload"]
    assert validate_payload(payload, known_keys(users[0])) == []
    assert payload["pick_sources"] == ["fallback"] * 3                         # the model was down
    assert [d["is_rest"] for d in payload["days"]] == [False, True, False, True, False, True, True]
    first = payload["days"][0]["exercises"][0]
    assert (first["sets"], first["reps_min"], first["reps_max"]) == (2, 8, 12)    # a beginner (D-049)
    with admin_transaction("test: no plan may exist yet") as conn:
        assert conn.execute("select count(*) from public.workout_plans where user_id = %s", (users[0],)).fetchone()[0] == 0


def test_only_equipment_the_user_owns_is_used(client, users):
    onboard(client)                                  # trains at home with no equipment
    client.put("/splits/choice", json={"split_key": "full_body_3"})
    payload = client.post("/plans/workout/generate").json()["payload"]
    keys = {e["exercise_key"] for d in payload["days"] for e in d["exercises"]}
    with user_transaction(users[0]) as conn:
        by_key = {o.key: o for o in list_exercises(conn)}
    assert keys and all(by_key[k].equipment == () and by_key[k].difficulty == "beginner" for k in keys)


def test_a_double_tap_reuses_the_proposal_and_a_later_one_replaces_it(client, users):
    onboard(client)
    client.put("/splits/choice", json={"split_key": "full_body_3"})
    first = client.post("/plans/workout/generate").json()
    again = client.post("/plans/workout/generate").json()
    assert again["id"] == first["id"] and pending_count(users[0]) == 1

    with admin_transaction("test: make the proposal look old") as conn:
        conn.execute("update public.plan_proposals set created_at = now() - interval '5 minutes' where user_id = %s", (users[0],))
    newer = client.post("/plans/workout/generate").json()
    assert newer["id"] != first["id"] and pending_count(users[0]) == 1          # the old one was expired, not left pending
    with admin_transaction("test: read old status") as conn:
        status = conn.execute("select status from public.plan_proposals where id = %s", (first["id"],)).fetchone()[0]
    assert status == "expired"


def test_pending_list_shows_only_my_proposals(client, users):
    onboard(client)
    client.put("/splits/choice", json={"split_key": "full_body_3"})
    mine = client.post("/plans/workout/generate").json()["id"]
    assert [p["id"] for p in client.get("/plans/proposals/pending").json()["proposals"]] == [mine]
    client.session.user_id = users[1]                # a different signed-in user
    assert client.get("/plans/proposals/pending").json() == {"proposals": []}


def test_too_few_safe_exercises_means_a_polite_refusal_not_a_thin_plan(client):
    onboard(client)
    client.put("/splits/choice", json={"split_key": "full_body_3"})
    with admin_transaction("test: give the user every injury") as conn:
        conn.execute(
            "update public.health_screening set injury_areas = %s where user_id = %s",
            (["knee", "shoulder", "lower_back", "wrist", "elbow", "hip", "ankle", "neck"], client.session.user_id),
        )
    response = client.post("/plans/workout/generate")
    assert response.status_code == 409
    assert "not enough safe exercises for: Full body A, Full body B, Full body C" in response.json()["detail"]
    assert pending_count(client.session.user_id) == 0
