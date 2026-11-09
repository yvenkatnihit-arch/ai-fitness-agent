"""GET and PATCH /profile against the real database: same validation as onboarding, history kept, targets recalculated."""

from datetime import date

import pytest

from app.calc.age import age_on
from app.calc.engine import BodyProfile, calculate_targets
from app.core.time import india_today
from app.db import admin_transaction
from app.llm.client import LLMBusy
from tests.db.test_onboarding_complete import FORMS, client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


def q(sql, *args):
    with admin_transaction("test: read") as conn:
        return conn.execute(sql, args).fetchall()


def expected(weight=58.0, goal="fat_loss", pace="normal", flags=frozenset(), sex="female", activity="light", height=162.5):
    return calculate_targets(BodyProfile(
        weight_kg=weight, height_cm=height, age_years=age_on(date(1995, 8, 20), india_today()), sex=sex,
        activity_level=activity, goal=goal, screening_flags=frozenset(flags), pace=pace))


def targets_rows(user_id):
    return q("select calorie_target_kcal, protein_g, focus_on_habits, goal_id from public.calculated_targets where user_id = %s order by effective_from",
             user_id)


def goals(user_id):
    return q("select goal_type, active, start_weight_kg, started_on, target_weight_kg, pace from public.goals where user_id = %s order by created_at", user_id)


def test_not_available_before_onboarding_finishes(client):
    client.put("/onboarding/consent", json=FORMS["consent"])
    assert client.get("/profile").status_code == 409
    response = client.patch("/profile", json={"weight_kg": 70})
    assert response.status_code == 409 and "finish onboarding" in response.json()["detail"]


def test_get_returns_the_answers_given_in_onboarding(client):
    onboard(client)
    p = client.get("/profile").json()
    assert (p["sex"], p["height_cm"], p["weight_kg"], p["activity_level"]) == ("female", 162.5, 58.0, "light")
    assert (p["goal_type"], p["target_weight_kg"], p["pace"]) == ("fat_loss", 54.0, "normal")
    assert (p["diet_type"], p["cuisine"], p["experience_level"], p["workout_location"], p["days_per_week"]) == ("vegetarian", "indian", "beginner", "home", 3)
    assert p["session_minutes"] == 45 and p["diabetes"] is False and p["injury_areas"] == []


def test_a_new_weight_updates_the_weigh_in_and_recalculates_the_targets_with_the_engine(client, users):
    onboard(client)
    response = client.patch("/profile", json={"weight_kg": 74})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["changed"] == ["weight_kg"] and body["profile"]["weight_kg"] == 74.0
    assert body["targets_recalculated"] is True and body["meal_plan_stale"] is True and body["workout_plan_stale"] is False
    want = expected(weight=74.0)
    assert body["targets"]["calorie_target_kcal"] == round(want.calorie_target_kcal) and body["targets"]["protein_g"] == round(want.protein_g)
    assert any("targets were updated" in m for m in body["messages"])
    rows = targets_rows(users[0])
    assert len(rows) == 2 and float(rows[1][0]) == pytest.approx(want.calorie_target_kcal, abs=0.1)      # history kept: old row stays
    assert float(q("select weight_kg from public.body_weight_entries where user_id = %s and measured_on = %s", users[0], india_today())[0][0]) == 74.0
    assert client.get("/targets/current").json()["calorie_target_kcal"] == round(want.calorie_target_kcal)


def test_nothing_is_written_when_nothing_changed(client, users):
    onboard(client)
    for patch in ({"weight_kg": 58}, {"weight_kg": 58.0, "diet_type": "vegetarian"}, {"display_name": None}):
        body = client.patch("/profile", json=patch).json()
        assert body["changed"] == [] and body["targets_recalculated"] is False and body["messages"] == [] and body["targets"] is None
    assert len(targets_rows(users[0])) == 1
    empty = client.patch("/profile", json={})
    assert empty.status_code == 422 and empty.json()["detail"] == "Nothing to change."


def test_a_pace_change_keeps_the_goal_start_and_recalculates(client, users):
    onboard(client)
    before = goals(users[0])
    body = client.patch("/profile", json={"pace": "slow"}).json()
    assert body["changed"] == ["pace"] and body["workout_plan_stale"] is True and body["meal_plan_stale"] is True
    after = goals(users[0])
    assert len(after) == 1 and after[0][1] is True and after[0][5] == "slow"
    assert (after[0][2], after[0][3]) == (before[0][2], before[0][3])             # start weight and date are untouched
    assert body["targets"]["calorie_target_kcal"] == round(expected(pace="slow").calorie_target_kcal)
    assert body["targets"]["calorie_target_kcal"] > round(expected().calorie_target_kcal)    # slow = a smaller deficit


def test_a_target_weight_change_does_not_touch_the_daily_numbers(client, users):
    onboard(client)
    body = client.patch("/profile", json={"target_weight_kg": 52}).json()
    assert body["changed"] == ["target_weight_kg"] and body["targets_recalculated"] is False
    assert body["workout_plan_stale"] is False and body["meal_plan_stale"] is False
    assert float(goals(users[0])[0][4]) == 52.0 and len(targets_rows(users[0])) == 1


def test_a_new_goal_type_closes_the_old_goal_and_starts_a_new_one(client, users):
    onboard(client)
    body = client.patch("/profile", json={"goal_type": "muscle_gain", "target_weight_kg": 63}).json()
    assert set(body["changed"]) == {"goal_type", "target_weight_kg"} and body["workout_plan_stale"] is True
    rows = goals(users[0])
    assert [(r[0], r[1]) for r in rows] == [("fat_loss", False), ("muscle_gain", True)]       # history kept, exactly one active
    assert float(rows[1][2]) == 58.0 and rows[1][3] == india_today()                          # starts from today's weight
    assert targets_rows(users[0])[-1][3] != targets_rows(users[0])[0][3]                      # the new targets point at the new goal
    assert body["targets"]["calorie_target_kcal"] == round(expected(goal="muscle_gain").calorie_target_kcal)


def test_a_target_weight_on_the_wrong_side_is_refused_and_nothing_changes(client, users):
    onboard(client)                                              # fat loss, target 54, weight 58
    response = client.patch("/profile", json={"goal_type": "muscle_gain"})     # a muscle-gain target of 54 would be a loss
    assert response.status_code == 422 and response.json()["detail"]
    again = client.patch("/profile", json={"weight_kg": 50})       # now the fat-loss target (54) is above the new weight
    assert again.status_code == 422
    assert client.get("/profile").json()["weight_kg"] == 58.0 and len(targets_rows(users[0])) == 1
    assert [(r[0], r[1]) for r in goals(users[0])] == [("fat_loss", True)]


def test_a_diet_change_makes_only_the_meal_plan_stale(client, users):
    onboard(client)
    body = client.patch("/profile", json={"diet_type": "vegan", "disliked_foods": ["Karela", "karela", "Bhindi"]}).json()
    assert set(body["changed"]) == {"diet_type", "disliked_foods"}
    assert body["meal_plan_stale"] is True and body["workout_plan_stale"] is False and body["targets_recalculated"] is False
    assert body["profile"]["disliked_foods"] == ["Karela", "Bhindi"]              # the same clean-up as onboarding
    assert len(targets_rows(users[0])) == 1


def test_a_health_flag_changes_targets_and_everything_goes_stale(client, users):
    onboard(client, pace="fast")
    fast = client.get("/targets/current").json()["calorie_target_kcal"]
    body = client.patch("/profile", json={"diabetes": True}).json()
    assert body["changed"] == ["diabetes"] and body["workout_plan_stale"] and body["meal_plan_stale"] and body["targets_recalculated"]
    want = expected(pace="fast", flags={"diabetes"})
    assert body["targets"]["calorie_target_kcal"] == round(want.calorie_target_kcal) != fast       # a milder deficit with a flag
    assert body["targets"]["doctor_note"]


def test_eating_disorder_history_gets_no_numbers_in_the_edit_response_either(client, users):
    onboard(client)
    body = client.patch("/profile", json={"eating_disorder_history": True}).json()
    assert body["targets"]["focus_on_habits"] is True
    assert body["targets"]["calorie_target_kcal"] is None and body["targets"]["protein_g"] is None
    assert targets_rows(users[0])[-1][2] is True                                   # stored as habits-only too


@pytest.mark.parametrize("patch,field", [
    ({"date_of_birth": "2012-01-01"}, "date_of_birth"),                            # under 18
    ({"date_of_birth": "2999-01-01"}, "date_of_birth"),
    ({"weight_kg": 20}, "weight_kg"),
    ({"height_cm": 400}, "height_cm"),
    ({"diet_type": "keto"}, "diet_type"),
    ({"experience_level": "pro"}, "experience_level"),
    ({"days_per_week": 9}, "days_per_week"),
    ({"session_minutes": 50}, "session_minutes"),
    ({"equipment": ["jetpack"]}, "equipment.0"),
    ({"injury_areas": ["elbow", "tentacle"]}, "injury_areas.1"),
    ({"diabetes": "yes"}, "diabetes"),
    ({"consent_at": "2026-01-01"}, "consent_at"),                                  # not editable here
    ({"onboarded_at": None}, "onboarded_at"),
])
def test_invalid_changes_get_the_same_field_errors_as_onboarding_and_change_nothing(client, users, patch, field):
    onboard(client)
    response = client.patch("/profile", json=patch)
    assert response.status_code == 422, response.text
    assert field in [e["field"] for e in response.json()["errors"]]
    assert len(targets_rows(users[0])) == 1 and client.get("/profile").json()["weight_kg"] == 58.0


def test_an_account_from_before_the_session_question_can_still_edit_training(client, users):
    onboard(client)
    with admin_transaction("test: pretend this account predates the session-length question") as conn:
        conn.execute("update public.profiles set session_minutes = null where id = %s", (users[0],))
    assert client.get("/profile").json()["session_minutes"] is None
    body = client.patch("/profile", json={"equipment": ["dumbbells"]}).json()
    assert body["changed"] == ["equipment"] and body["profile"]["session_minutes"] == 60        # the app default fills the gap
    assert client.patch("/profile", json={"session_minutes": 30}).json()["profile"]["session_minutes"] == 30


def test_each_person_edits_only_their_own_profile(client, users):
    onboard(client)
    client.session.user_id = users[1]
    assert client.patch("/profile", json={"weight_kg": 90}).status_code == 409           # not onboarded: nothing to edit
    client.session.user_id = users[0]
    assert client.get("/profile").json()["weight_kg"] == 58.0


def test_editing_never_touches_an_active_plan(client, users, monkeypatch):
    """A meal plan stays exactly as approved; the response only says it no longer matches."""
    def down(user_id):
        def ask(prompt):
            raise LLMBusy()
        return ask
    monkeypatch.setattr("app.workflows.pick_meals._default_ask", down)
    onboard(client)
    proposal = client.post("/plans/meal/generate").json()
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200
    plan_before = client.get("/plans/meal/active").json()
    body = client.patch("/profile", json={"diet_type": "vegan"}).json()
    assert body["meal_plan_stale"] is True
    assert client.get("/plans/meal/active").json() == plan_before               # still the approved plan, unchanged
