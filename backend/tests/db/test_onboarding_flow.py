"""The whole onboarding against Supabase, as a real (throwaway) user under RLS."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.core.time import india_today
from app.db import admin_transaction, close_pool
from app.main import app

pytestmark = pytest.mark.db

CONSENT = {"health_data_consent": True, "privacy_notice_version": "2026-11"}
BASICS = {"date_of_birth": "1995-08-20", "sex": "female", "height_cm": 162.5, "weight_kg": 58.0,
          "activity_level": "light", "display_name": "Test User"}
GOAL = {"goal_type": "fat_loss", "target_weight_kg": 54}
PREFS = {"diet_type": "vegetarian", "disliked_foods": ["Karela"]}
TRAINING = {"experience_level": "beginner", "workout_location": "home",
            "equipment": ["dumbbells", "yoga_mat"], "days_per_week": 3, "session_minutes": 45}
SCREENING = {"pregnant_or_breastfeeding": False, "diabetes": False, "heart_or_bp": False, "kidney": False,
             "recent_surgery_or_injury": False, "eating_disorder_history": False, "injury_areas": ["knee"]}


@pytest.fixture
def user_id():
    """A committed throwaway auth user (no profile yet). Deleted afterwards; deletes cascade."""
    uid = uuid.uuid4()
    with admin_transaction("test setup: create scratch user") as conn:
        conn.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"scratch-{uid}@example.test"))
    try:
        yield uid
    finally:
        with admin_transaction("test cleanup: delete scratch user") as conn:
            conn.execute("delete from auth.users where id = %s", (uid,))


@pytest.fixture
def client(user_id):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id, email=None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    close_pool()


def test_fresh_user_starts_at_consent(client):
    status = client.get("/onboarding/status").json()
    assert status["next_step"] == "consent"
    assert not any(status[step] for step in ("consent", "basics", "goal", "preferences", "training", "screening"))


def test_nothing_can_be_saved_before_consent(client):
    response = client.put("/onboarding/basics", json=BASICS)
    assert response.status_code == 409
    assert response.json()["detail"] == "Please accept the privacy notice first."


def test_goal_needs_basics_first(client):
    client.put("/onboarding/consent", json=CONSENT)
    response = client.put("/onboarding/goal", json=GOAL)
    assert response.status_code == 409
    assert response.json()["detail"] == "Please fill in your basic details first."


def test_full_onboarding_in_order(client, user_id):
    steps = [("consent", CONSENT, "basics"), ("basics", BASICS, "goal"), ("goal", GOAL, "preferences"),
             ("preferences", PREFS, "training"), ("training", TRAINING, "screening"),
             ("screening", SCREENING, "complete")]
    for path, body, expected_next in steps:
        response = client.put(f"/onboarding/{path}", json=body)
        assert response.status_code == 200, (path, response.json())
        assert response.json()["next_step"] == expected_next

    with admin_transaction("test: check what was saved") as conn:
        profile = conn.execute(
            "select display_name, sex, height_cm, diet_type, equipment, days_per_week, session_minutes, consent_version"
            " from public.profiles where id = %s", (user_id,)
        ).fetchone()
        weight = conn.execute(
            "select measured_on, weight_kg from public.body_weight_entries where user_id = %s", (user_id,)
        ).fetchone()
        goal = conn.execute(
            "select goal_type, start_weight_kg, target_weight_kg from public.goals where user_id = %s and active",
            (user_id,),
        ).fetchone()
    assert profile[0] == "Test User" and profile[1] == "female" and float(profile[2]) == 162.5
    assert profile[3:] == ("vegetarian", ["dumbbells", "yoga_mat"], 3, 45, "2026-11")
    assert weight[0] == india_today() and float(weight[1]) == 58.0  # today's weigh-in, India date
    assert goal[0] == "fat_loss" and float(goal[1]) == 58.0 and float(goal[2]) == 54.0


def test_pace_and_cuisine_are_saved_and_pace_can_be_changed(client, user_id):
    client.put("/onboarding/consent", json=CONSENT)
    client.put("/onboarding/basics", json=BASICS)
    assert client.put("/onboarding/goal", json={**GOAL, "pace": "fast"}).status_code == 200
    assert client.put("/onboarding/preferences", json={**PREFS, "cuisine": "indian"}).status_code == 200

    def saved():
        with admin_transaction("test: check pace and cuisine") as conn:
            pace = conn.execute("select pace from public.goals where user_id = %s and active", (user_id,)).fetchone()[0]
            cuisine = conn.execute("select cuisine from public.profiles where id = %s", (user_id,)).fetchone()[0]
        return pace, cuisine

    assert saved() == ("fast", "indian")
    client.put("/onboarding/goal", json={**GOAL, "pace": "slow"})   # changing it updates the same goal
    assert saved() == ("slow", "indian")
    client.put("/onboarding/goal", json=GOAL)                       # not sent: back to the default
    assert saved()[0] == "normal"


def test_unknown_pace_or_cuisine_is_a_422_and_saves_nothing(client, user_id):
    client.put("/onboarding/consent", json=CONSENT)
    client.put("/onboarding/basics", json=BASICS)
    assert client.put("/onboarding/goal", json={**GOAL, "pace": "extreme"}).status_code == 422
    assert client.put("/onboarding/preferences", json={**PREFS, "cuisine": "martian"}).status_code == 422


def test_fat_loss_target_above_current_weight_is_refused(client):
    client.put("/onboarding/consent", json=CONSENT)
    client.put("/onboarding/basics", json=BASICS)  # 58 kg
    response = client.put("/onboarding/goal", json={"goal_type": "fat_loss", "target_weight_kg": 62})
    assert response.status_code == 422
    assert "below your current weight" in response.json()["detail"]


def test_saving_a_step_twice_updates_it(client, user_id):
    client.put("/onboarding/consent", json=CONSENT)
    client.put("/onboarding/basics", json=BASICS)
    client.put("/onboarding/basics", json={**BASICS, "weight_kg": 57.4})
    client.put("/onboarding/goal", json=GOAL)
    client.put("/onboarding/goal", json={"goal_type": "recomp"})
    with admin_transaction("test: check updates") as conn:
        weights = conn.execute(
            "select weight_kg from public.body_weight_entries where user_id = %s", (user_id,)
        ).fetchall()
        goals = conn.execute(
            "select goal_type, target_weight_kg from public.goals where user_id = %s and active", (user_id,)
        ).fetchall()
    assert [float(w[0]) for w in weights] == [57.4]  # still one weigh-in for today
    assert goals == [("recomp", None)]               # still one active goal


def test_steps_are_locked_after_onboarding_finishes(client, user_id):
    client.put("/onboarding/consent", json=CONSENT)
    with admin_transaction("test: mark onboarding finished") as conn:
        conn.execute("update public.profiles set onboarded_at = now() where id = %s", (user_id,))
    for path, body in (("basics", BASICS), ("consent", CONSENT)):
        response = client.put(f"/onboarding/{path}", json=body)
        assert response.status_code == 409
        assert "already complete" in response.json()["detail"]
    assert client.get("/onboarding/status").json()["next_step"] == "done"
