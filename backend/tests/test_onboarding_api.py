"""Onboarding endpoints refuse bad requests BEFORE touching the database (no DB needed here)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app import db
from app.core.auth import CurrentUser, get_current_user
from app.main import app


@pytest.fixture
def client(monkeypatch):
    def no_db(*args, **kwargs):
        raise AssertionError("this request should have been refused before any database work")

    monkeypatch.setattr("app.api.onboarding.user_transaction", no_db)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid.uuid4(), email=None)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path",
    ["/onboarding/consent", "/onboarding/basics", "/onboarding/goal",
     "/onboarding/preferences", "/onboarding/training", "/onboarding/screening"],
)
def test_every_step_needs_a_login(path):
    response = TestClient(app).put(path, json={})
    assert response.status_code == 401


def test_status_needs_a_login():
    assert TestClient(app).get("/onboarding/status").status_code == 401


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/onboarding/consent", {"health_data_consent": False, "privacy_notice_version": "2026-11"}),
        ("/onboarding/basics", {"date_of_birth": "2015-01-01", "sex": "male", "height_cm": 150,
                                "weight_kg": 40, "activity_level": "light"}),  # under 18
        ("/onboarding/basics", {"date_of_birth": "1990-01-01", "sex": "male", "height_cm": 175,
                                "weight_kg": 70, "activity_level": "light", "user_id": "x"}),  # extra field
        ("/onboarding/goal", {"goal_type": "bulk"}),
        ("/onboarding/screening", {"diabetes": "yes"}),
    ],
)
def test_bad_bodies_get_422_without_touching_the_database(client, path, body):
    response = client.put(path, json=body)
    assert response.status_code == 422
