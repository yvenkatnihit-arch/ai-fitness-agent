"""Step 8.1 (D-105): GET /dashboard/today against the real database (plans made by code, no model)."""

from datetime import date

import pytest

from app.db import admin_transaction
from app.llm.client import LLMBusy
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db

WEDNESDAY = date(2026, 11, 11)


@pytest.fixture(autouse=True)
def models_are_down(monkeypatch):
    def down(user_id):
        def ask(prompt):
            raise LLMBusy()
        return ask
    monkeypatch.setattr("app.workflows.pick_meals._default_ask", down)
    monkeypatch.setattr("app.workflows.pick_exercises._default_ask", down)


def food_id(key):
    with admin_transaction("test: food id") as conn:
        return conn.execute("select id from public.foods where key = %s", (key,)).fetchone()[0]


def approve_plans(client):
    for kind in ("meal", "workout"):
        proposal = client.post(f"/plans/{kind}/generate").json()
        assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200


def test_a_new_user_sees_targets_progress_at_zero_and_no_plans(client, users):
    onboard(client)
    body = client.get("/dashboard/today").json()
    targets = client.get("/targets/current").json()
    assert body["numbers_hidden"] is False and body["logged"] == [] and body["meal_plan"] is None and body["workout"] is None
    assert body["progress"]["kcal"] == {"eaten": 0.0, "target": float(targets["calorie_target_kcal"]), "percent": 0}
    assert body["progress"]["protein_g"]["target"] == float(targets["protein_g"])


def test_logging_a_meal_moves_the_progress_by_exactly_what_was_logged(client, users):
    onboard(client)
    logged = client.post("/meals", json={"slot": "lunch", "items": [
        {"food_id": food_id("roti"), "quantity": 2, "unit": "piece"}, {"food_id": food_id("sambar"), "quantity": 1, "unit": "katori"}]}).json()
    body = client.get("/dashboard/today").json()
    target = body["progress"]["kcal"]["target"]
    assert body["progress"]["kcal"]["eaten"] == round(logged["totals"]["kcal"], 1)
    assert body["progress"]["kcal"]["percent"] == round(logged["totals"]["kcal"] / target * 100)
    assert body["progress"]["protein_g"]["eaten"] == round(logged["totals"]["protein_g"], 1)
    assert [(m["slot"], len(m["foods"])) for m in body["logged"]] == [("lunch", 2)]
    assert body["logged"][0]["foods"][0].startswith("Roti") and body["logged"][0]["foods"][0].endswith("(2 piece)")


def test_todays_planned_meals_and_workout_match_the_plan_screens(client, users, monkeypatch):
    monkeypatch.setattr("app.workflows.dashboard.india_today", lambda: WEDNESDAY)
    onboard(client)
    approve_plans(client)
    body = client.get("/dashboard/today").json()
    assert body["weekday"] == "Wednesday" and body["date"] == "2026-11-11"
    wednesday = next(d for d in client.get("/plans/meal/active").json()["days"] if d["day_of_week"] == 3)
    assert [(m["slot"], [i["name"] for i in m["items"]]) for m in body["meal_plan"]["meals"]] == \
        [(m["slot"], [i["name"] for i in m["items"]]) for m in wednesday["meals"]]
    assert body["meal_plan"]["kcal"] == wednesday["totals"]["kcal"]
    day = next(d for d in client.get("/plans/workout/active").json()["days"] if d["day_of_week"] == 3)
    if day["is_rest"]:
        assert body["workout"] == {"rest_day": True, "focus": None, "minutes": None, "exercises": []}
    else:
        assert body["workout"]["focus"] == day["focus"] and body["workout"]["minutes"] == day["minutes"]
        assert [e["name"] for e in body["workout"]["exercises"]] == [e["name"] for e in day["exercises"]]


def test_a_user_who_must_not_see_numbers_gets_none_anywhere(client, users):
    onboard(client, eating_disorder_history=True)
    approve_plans(client)
    client.post("/meals", json={"slot": "lunch", "items": [{"food_id": food_id("roti"), "quantity": 2, "unit": "piece"}]})
    body = client.get("/dashboard/today").json()
    assert body["numbers_hidden"] is True and body["progress"] is None and body["meal_plan"]["kcal"] is None
    assert body["logged"] and body["meal_plan"]["meals"]                                  # the foods are still shown
    assert all(i["kcal"] is None for m in body["meal_plan"]["meals"] for i in m["items"])


def test_nobody_sees_anyone_elses_dashboard(client, users):
    onboard(client)
    client.post("/meals", json={"slot": "lunch", "items": [{"food_id": food_id("roti"), "quantity": 2, "unit": "piece"}]})
    client.session.user_id = users[1]                                                     # never onboarded: no targets, no logs of their own
    other = client.get("/dashboard/today").json()
    assert other["progress"] is None and other["logged"] == [] and other["meal_plan"] is None


def test_the_dashboard_needs_a_login(users):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anonymous:                                                    # no login override here
        assert anonymous.get("/dashboard/today").status_code in (401, 403)
