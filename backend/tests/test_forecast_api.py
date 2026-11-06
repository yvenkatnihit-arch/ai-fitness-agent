"""The forecast endpoint with the database replaced by a fake."""

import contextlib
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.db.targets import SavedInputs
from app.main import app


def saved(**changes) -> SavedInputs:
    base = dict(goal_id=uuid.uuid4(), goal_type="fat_loss", weight_kg=80.0, height_cm=180.0,
                date_of_birth=date(1990, 1, 1), sex="male", activity_level="moderate", pace="normal",
                target_weight_kg=75.0, flags=frozenset())
    return SavedInputs(**{**base, **changes})


@pytest.fixture
def fake(monkeypatch):
    state = {"saved": saved()}
    monkeypatch.setattr("app.api.targets.user_transaction", lambda user_id: contextlib.nullcontext(object()))
    monkeypatch.setattr("app.api.targets.repo.read_inputs", lambda conn: state["saved"])
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid.uuid4(), email=None)
    yield state
    app.dependency_overrides.clear()


def test_needs_a_login():
    assert TestClient(app).get("/targets/forecast").status_code == 401


def test_a_ready_forecast_has_dates_in_order_a_message_and_the_estimate_note(fake):
    body = TestClient(app).get("/targets/forecast").json()
    assert body["status"] == "ready" and body["current_weight_kg"] == 80.0 and body["target_weight_kg"] == 75.0
    assert body["earliest"] < body["likely"] < body["latest"]
    assert body["message"].startswith("At this pace you could reach 75 kg around ")
    assert "estimate" in body["note"] and body["weeks_likely"] >= 10
    assert body["weekly_change_kg"] < 0


def test_no_target_weight_gives_a_helpful_message_and_no_dates(fake):
    fake["saved"] = saved(target_weight_kg=None)
    body = TestClient(app).get("/targets/forecast").json()
    assert body["status"] == "no_target" and body["likely"] is None and body["note"] is None
    assert "Set a target weight" in body["message"]


def test_eating_disorder_history_gets_no_weights_or_dates_at_all(fake):
    fake["saved"] = saved(flags=frozenset({"eating_disorder_history"}))
    body = TestClient(app).get("/targets/forecast").json()
    assert body["status"] == "habits_only" and body["message"].startswith("Your plan focuses on healthy habits")
    assert body["current_weight_kg"] is None and body["target_weight_kg"] is None and body["weekly_change_kg"] is None
    assert body["earliest"] is None and body["likely"] is None


def test_before_onboarding_is_a_404(fake):
    fake["saved"] = None
    assert TestClient(app).get("/targets/forecast").status_code == 404
