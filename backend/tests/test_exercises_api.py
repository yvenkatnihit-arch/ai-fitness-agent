"""The exercise endpoint with the database replaced by small fakes."""

import contextlib
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.calc.exercise_filter import ExerciseOption
from app.core.auth import CurrentUser, get_current_user
from app.db.exercises import TrainingContext
from app.main import app

SQUAT = ExerciseOption(1, "bodyweight_squat", "Bodyweight Squat", ("quads",), (), "both", "beginner", "squat",
                       ("Sit back", "Chest up"), ("knee",), "review")
PLANK = replace(SQUAT, id=2, key="plank", name="Plank", movement_pattern="core", contraindications=("wrist",))
DEADBUG = replace(SQUAT, id=3, key="dead_bug", name="Dead Bug", movement_pattern="core", contraindications=(),
                  review_status="ready")
BARBELL = replace(SQUAT, id=4, key="back_squat", name="Back Squat", equipment=("barbell",), location="gym",
                  difficulty="intermediate", contraindications=())


@pytest.fixture
def fake(monkeypatch):
    state = {"context": TrainingContext("beginner", "gym", frozenset(), frozenset()), "library": [SQUAT, PLANK, DEADBUG, BARBELL]}
    monkeypatch.setattr("app.api.exercises.user_transaction", lambda user_id: contextlib.nullcontext(object()))
    monkeypatch.setattr("app.api.exercises.repo.read_training_context", lambda conn: state["context"])
    monkeypatch.setattr("app.api.exercises.repo.list_exercises", lambda conn: state["library"])
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid.uuid4(), email=None)
    yield state
    app.dependency_overrides.clear()


def test_needs_a_login():
    assert TestClient(app).get("/exercises/for-me").status_code == 401


def test_injured_users_do_not_get_tagged_exercises(fake):
    fake["context"] = TrainingContext("beginner", "gym", frozenset(), frozenset({"knee"}))
    body = TestClient(app).get("/exercises/for-me").json()
    assert [e["key"] for e in body["exercises"]] == ["plank", "dead_bug"]
    assert body["injuries"] == ["knee"] and body["total_in_library"] == 4 and body["shown"] == 2


def test_level_hides_harder_exercises_and_verified_reflects_signoff(fake):
    body = TestClient(app).get("/exercises/for-me").json()
    by_key = {e["key"]: e for e in body["exercises"]}
    assert "back_squat" not in by_key                                  # intermediate, user is a beginner
    assert by_key["dead_bug"]["verified"] is True and by_key["plank"]["verified"] is False
    assert by_key["plank"]["form_cues"] == ["Sit back", "Chest up"]


def test_home_setting_uses_owned_equipment(fake):
    fake["context"] = TrainingContext("intermediate", "both", frozenset(), frozenset())
    assert [e["key"] for e in TestClient(app).get("/exercises/for-me").json()["exercises"]][-1] == "back_squat"  # 'both' defaults to gym
    body = TestClient(app).get("/exercises/for-me", params={"setting": "home"}).json()
    assert body["setting"] == "home" and "back_squat" not in {e["key"] for e in body["exercises"]}


def test_unfinished_onboarding_gets_409_and_never_lists_the_library(fake):
    fake["context"] = None
    fake["library"] = None  # would crash if the endpoint tried to use it
    assert TestClient(app).get("/exercises/for-me").status_code == 409


def test_bad_setting_is_422(fake):
    assert TestClient(app).get("/exercises/for-me", params={"setting": "moon"}).status_code == 422
