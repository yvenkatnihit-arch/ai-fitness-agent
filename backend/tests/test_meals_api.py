"""Meal logging refuses bad requests before touching the database (no DB needed here)."""

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.meals import check_log_date
from app.core.auth import CurrentUser, get_current_user
from app.main import app

GOOD = {"slot": "lunch", "items": [{"food_id": 1, "quantity": 2, "unit": "piece"}]}


@pytest.fixture
def client(monkeypatch):
    def no_db(*args, **kwargs):
        raise AssertionError("this request should have been refused before any database work")

    monkeypatch.setattr("app.api.meals.user_transaction", no_db)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid.uuid4(), email=None)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(("method", "path"), [("post", "/meals"), ("get", "/meals"),
                                              ("delete", f"/meals/{uuid.uuid4()}")])
def test_meal_endpoints_need_a_login(method, path):
    kwargs = {"json": GOOD} if method == "post" else {}
    assert getattr(TestClient(app), method)(path, **kwargs).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {**GOOD, "slot": "brunch"},
        {**GOOD, "items": []},
        {**GOOD, "items": [{"food_id": 1, "quantity": 1, "unit": "g"}] * 21},
        {**GOOD, "items": [{"food_id": 1, "quantity": 0, "unit": "g"}]},
        {**GOOD, "items": [{"food_id": 1, "quantity": 1, "unit": "bucket"}]},
        {**GOOD, "items": [{"food_id": 1, "quantity": 1, "unit": "g", "kcal": 5}]},  # nutrition is never client-sent
        {**GOOD, "user_id": str(uuid.uuid4())},
        {**GOOD, "logged_on": "2999-01-01"},                                          # future
        {**GOOD, "logged_on": "2020-01-01"},                                          # too far back
    ],
)
def test_bad_meals_get_422_without_touching_the_database(client, body):
    assert client.post("/meals", json=body).status_code == 422


def test_log_date_window():
    today = date(2026, 11, 6)
    check_log_date(today, today)
    check_log_date(date(2026, 10, 30), today)  # 7 days back is allowed
    for day in (date(2026, 11, 7), date(2026, 10, 29)):
        with pytest.raises(HTTPException):
            check_log_date(day, today)
