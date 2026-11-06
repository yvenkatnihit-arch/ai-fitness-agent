"""The split recommendation endpoint with the database replaced by a fake."""

import contextlib
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.db.splits import SplitInputs
from app.main import app


@pytest.fixture
def fake(monkeypatch):
    state = {"inputs": SplitInputs(4, "intermediate", "muscle_gain")}
    monkeypatch.setattr("app.api.splits.user_transaction", lambda user_id: contextlib.nullcontext(object()))
    monkeypatch.setattr("app.api.splits.repo.read_split_inputs", lambda conn: state["inputs"])
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid.uuid4(), email=None)
    yield state
    app.dependency_overrides.clear()


def test_needs_a_login():
    assert TestClient(app).get("/splits/recommend").status_code == 401


def test_recommends_for_the_saved_days_level_and_goal(fake):
    body = TestClient(app).get("/splits/recommend").json()
    assert (body["days_per_week"], body["level"], body["goal"]) == (4, "intermediate", "muscle_gain")
    first = body["recommendations"][0]
    assert first["key"] == "upper_lower_4" and first["fit"] == "best" and first["training_days"] == 4
    assert [d["label"] for d in first["schedule"]] == ["Upper body", "Lower body", "Upper body", "Lower body"]
    assert first["schedule"][0]["patterns"] == ["push_horizontal", "pull_horizontal", "push_vertical", "pull_vertical"]
    assert first["reasons"] and first["recovery_days"] == 0


def test_days_can_be_overridden_to_compare(fake):
    body = TestClient(app).get("/splits/recommend", params={"days": 6}).json()
    assert body["days_per_week"] == 6 and {r["key"] for r in body["recommendations"]} == {"ppl_6", "arnold_6"}


@pytest.mark.parametrize("days", [0, 8, "many"])
def test_bad_days_are_422(fake, days):
    assert TestClient(app).get("/splits/recommend", params={"days": days}).status_code == 422


def test_unfinished_onboarding_is_409(fake):
    fake["inputs"] = None
    response = TestClient(app).get("/splits/recommend")
    assert response.status_code == 409 and "goal and training" in response.json()["detail"]
