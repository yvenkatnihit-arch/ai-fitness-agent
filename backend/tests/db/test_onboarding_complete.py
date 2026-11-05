"""Finishing onboarding end to end, plus cross-user checks through the API (moved from Step 2.9)."""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.calc.age import age_on
from app.calc.engine import BodyProfile, calculate_targets
from app.core.auth import CurrentUser, get_current_user
from app.core.time import india_today
from app.db import admin_transaction, close_pool
from app.main import app
from app.schemas.targets import DOCTOR_NOTE, REASON_MESSAGES

pytestmark = pytest.mark.db

FORMS = {
    "consent": {"health_data_consent": True, "privacy_notice_version": "2026-11"},
    "basics": {"date_of_birth": "1995-08-20", "sex": "female", "height_cm": 162.5, "weight_kg": 58.0,
               "activity_level": "light"},
    "goal": {"goal_type": "fat_loss", "target_weight_kg": 54},
    "preferences": {"diet_type": "vegetarian", "disliked_foods": []},
    "training": {"experience_level": "beginner", "workout_location": "home", "equipment": [], "days_per_week": 3},
    "screening": {"pregnant_or_breastfeeding": False, "diabetes": False, "heart_or_bp": False, "kidney": False,
                  "recent_surgery_or_injury": False, "eating_disorder_history": False, "injury_areas": []},
}


class Session:
    """Who the API thinks is signed in. Tests switch users by setting .user_id."""

    user_id: uuid.UUID | None = None


@pytest.fixture
def users():
    """Two committed throwaway auth users. Deleted afterwards (cascades to everything they own)."""
    ids = [uuid.uuid4(), uuid.uuid4()]
    with admin_transaction("test setup: create scratch users") as conn:
        for uid in ids:
            conn.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"scratch-{uid}@example.test"))
    try:
        yield ids
    finally:
        with admin_transaction("test cleanup: delete scratch users") as conn:
            conn.execute("delete from auth.users where id = any(%s)", (ids,))


@pytest.fixture
def client(users):
    session = Session()
    session.user_id = users[0]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=session.user_id, email=None)
    with TestClient(app) as c:
        c.session = session
        yield c
    app.dependency_overrides.clear()
    close_pool()


def onboard(client, **screening):
    for step in ("consent", "basics", "goal", "preferences", "training"):
        assert client.put(f"/onboarding/{step}", json=FORMS[step]).status_code == 200
    body = {**FORMS["screening"], **screening}
    assert client.put("/onboarding/screening", json=body).status_code == 200
    return client.post("/onboarding/complete")


def expected(flags=frozenset()):
    """What the Phase 1 engine says for FORMS (age computed for today, like the API does)."""
    return calculate_targets(BodyProfile(
        weight_kg=58.0, height_cm=162.5, age_years=age_on(date(1995, 8, 20), india_today()),
        sex="female", activity_level="light", goal="fat_loss", screening_flags=frozenset(flags),
    ))


def test_complete_before_all_steps_lists_what_is_missing(client):
    client.put("/onboarding/consent", json=FORMS["consent"])
    client.put("/onboarding/basics", json=FORMS["basics"])
    response = client.post("/onboarding/complete")
    assert response.status_code == 409
    assert response.json()["detail"] == "Please finish these steps first: goal, preferences, training, screening."


def test_complete_returns_the_engines_numbers_and_saves_them(client, users):
    response = onboard(client)
    assert response.status_code == 200
    t = expected()
    assert response.json() == {
        "calorie_target_kcal": round(t.calorie_target_kcal), "protein_g": round(t.protein_g),
        "fat_g": round(t.fat_g), "carbs_g": round(t.carbs_g),
        "reasons": [REASON_MESSAGES[c] for c in t.reasons], "doctor_note": None, "focus_on_habits": False,
    }
    assert client.get("/onboarding/status").json()["next_step"] == "done"
    assert client.get("/targets/current").json() == response.json()  # same numbers after a reload

    with admin_transaction("test: check saved targets") as conn:
        rows = conn.execute(
            "select calorie_target_kcal, inputs->>'goal' from public.calculated_targets where user_id = %s",
            (users[0],),
        ).fetchall()
    assert len(rows) == 1
    assert float(rows[0][0]) == pytest.approx(t.calorie_target_kcal, abs=0.05)  # stored to 1 decimal
    assert rows[0][1] == "fat_loss"


def test_completing_twice_is_refused_and_saves_nothing_extra(client, users):
    assert onboard(client).status_code == 200
    again = client.post("/onboarding/complete")
    assert again.status_code == 409
    with admin_transaction("test: count targets") as conn:
        count = conn.execute(
            "select count(*) from public.calculated_targets where user_id = %s", (users[0],)
        ).fetchone()[0]
    assert count == 1


def test_kidney_flag_gives_doctor_note_and_protein_cap(client):
    body = onboard(client, kidney=True).json()
    assert body["doctor_note"] == DOCTOR_NOTE
    assert REASON_MESSAGES["kidney_protein_cap"] in body["reasons"]
    assert body["protein_g"] == round(expected({"kidney"}).protein_g)  # 58 kg * 0.8 = 46 g


def test_eating_disorder_history_shows_no_numbers(client):
    body = onboard(client, eating_disorder_history=True).json()
    assert body["focus_on_habits"] is True
    assert [body[k] for k in ("calorie_target_kcal", "protein_g", "fat_g", "carbs_g")] == [None] * 4
    assert client.get("/targets/current").json()["calorie_target_kcal"] is None  # hidden after reload too


def test_targets_before_onboarding_is_404(client):
    response = client.get("/targets/current")
    assert response.status_code == 404


# --- Cross-user checks through the API (moved from Step 2.9) ---

def test_another_user_cannot_see_or_affect_my_onboarding(client, users):
    alice, bob = users
    assert onboard(client).status_code == 200  # Alice finishes onboarding

    client.session.user_id = bob
    assert client.get("/targets/current").status_code == 404           # Bob sees no targets
    assert client.get("/onboarding/status").json()["next_step"] == "consent"  # Bob starts fresh
    assert client.put("/onboarding/basics", json=FORMS["basics"]).status_code == 409  # Bob hasn't consented

    client.put("/onboarding/consent", json=FORMS["consent"])
    client.put("/onboarding/basics", json={**FORMS["basics"], "weight_kg": 90})

    client.session.user_id = alice
    assert client.get("/onboarding/status").json()["next_step"] == "done"  # Alice unaffected
    with admin_transaction("test: check ownership") as conn:
        weights = dict(conn.execute(
            "select user_id, weight_kg from public.body_weight_entries where user_id = any(%s)", (users,)
        ).fetchall())
    assert float(weights[alice]) == 58.0 and float(weights[bob]) == 90.0
