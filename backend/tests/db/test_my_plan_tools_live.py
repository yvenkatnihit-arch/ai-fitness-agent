"""Step 7.12a (D-103): the "my plan" tools against the real database. Nothing here calls a model except as switched off (code picks the
dishes and exercises); the tools themselves never call one."""

from datetime import date

import pytest

from app.agents.context import RunContext
from app.agents.plan_tools import (GET_MY_MEAL_PLAN_DAY, GET_MY_TARGETS, GET_MY_WORKOUT_DAY, GET_TODAY_LOGGED, NO_MEAL_PLAN, NO_TARGETS,
                                   NO_WORKOUT_PLAN, DayArgs, NoArgs)
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


@pytest.fixture
def on_a_wednesday(monkeypatch):
    monkeypatch.setattr("app.agents.plan_tools.india_today", lambda: WEDNESDAY)


def run(tool, user, args=None):
    return tool.run(RunContext(user), args or (NoArgs() if tool in (GET_MY_TARGETS, GET_TODAY_LOGGED) else DayArgs()))


def approved_meal_plan(client):
    proposal = client.post("/plans/meal/generate").json()
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200


def approved_workout_plan(client):
    assert client.put("/splits/choice", json={"split_key": "full_body_3"}).status_code == 200
    proposal = client.post("/plans/workout/generate").json()
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200


def food_id(key):
    with admin_transaction("test: food id") as conn:
        return conn.execute("select id from public.foods where key = %s", (key,)).fetchone()[0]


# ---------- targets ----------

def test_targets_are_the_numbers_the_targets_screen_shows(client, users):
    onboard(client)
    shown = client.get("/targets/current").json()
    got = run(GET_MY_TARGETS, users[0])
    for key in ("calorie_target_kcal", "protein_g", "fat_g", "carbs_g", "reasons", "focus_on_habits"):
        assert got[key] == shown[key]
    assert "note" not in got


def test_a_user_who_must_not_see_numbers_gets_none_from_any_tool(client, users):
    onboard(client, eating_disorder_history=True)
    approved_meal_plan(client)
    client.post("/meals", json={"slot": "lunch", "items": [{"food_id": food_id("roti"), "quantity": 2, "unit": "piece"}]})
    targets = run(GET_MY_TARGETS, users[0])
    assert targets["focus_on_habits"] is True and "note" in targets
    assert not {"calorie_target_kcal", "protein_g", "fat_g", "carbs_g", "protein_pct"} & set(targets)
    meal = run(GET_MY_MEAL_PLAN_DAY, users[0], DayArgs(day="monday"))
    logged = run(GET_TODAY_LOGGED, users[0])
    for result in (meal, logged):
        text = repr(result).lower()
        assert not any(w in text for w in ("kcal", "protein_g", "carbs_g", "fat_g", "totals"))
    assert meal["meals"] and logged["meals_logged"] == 1 and "note" in logged            # the foods are still there, just no numbers


def test_without_onboarding_there_are_no_targets_and_it_says_so(client, users):
    assert run(GET_MY_TARGETS, users[1]) == {"error": NO_TARGETS}


# ---------- meal plan ----------

def test_a_meal_plan_day_matches_what_the_plan_screen_shows(client, users, on_a_wednesday):
    onboard(client)
    approved_meal_plan(client)
    shown = client.get("/plans/meal/active").json()
    wednesday = next(d for d in shown["days"] if d["day_of_week"] == 3)
    for name in ("wednesday", "today"):
        got = run(GET_MY_MEAL_PLAN_DAY, users[0], DayArgs(day=name))
        assert got["day"] == "Wednesday" and got["totals"] == wednesday["totals"]
        assert [(m["slot"], [i["name"] for i in m["items"]]) for m in got["meals"]] == [(m["slot"], [i["name"] for i in m["items"]]) for m in wednesday["meals"]]
        assert got["meals"][0]["items"][0]["text"] == wednesday["meals"][0]["items"][0]["text"]      # "1.5 katori (225 g)"
    assert run(GET_MY_MEAL_PLAN_DAY, users[0], DayArgs(day="tomorrow"))["day"] == "Thursday"


def test_no_meal_plan_says_where_to_make_one(client, users):
    onboard(client)
    assert run(GET_MY_MEAL_PLAN_DAY, users[0]) == {"error": NO_MEAL_PLAN}


# ---------- workout plan ----------

def test_a_workout_day_lists_exercises_and_at_most_three_form_cues(client, users, on_a_wednesday):
    onboard(client)
    approved_workout_plan(client)
    shown = client.get("/plans/workout/active").json()
    day = next(d for d in shown["days"] if not d["is_rest"])
    name = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[day["day_of_week"] - 1]
    got = run(GET_MY_WORKOUT_DAY, users[0], DayArgs(day=name))
    assert got["rest_day"] is False and got["focus"] == day["focus"] and got["about_minutes"] == day["minutes"]
    assert [e["name"] for e in got["exercises"]] == [e["name"] for e in day["exercises"]]
    first, shown_first = got["exercises"][0], day["exercises"][0]
    assert first["sets"] == shown_first["sets"] and first["reps"] == f"{shown_first['reps_min']}-{shown_first['reps_max']}"
    assert all(len(e["form_cues"]) <= 3 for e in got["exercises"])


def test_a_rest_day_is_reported_as_a_rest_day(client, users):
    onboard(client)
    approved_workout_plan(client)
    shown = client.get("/plans/workout/active").json()
    rest = next(d for d in shown["days"] if d["is_rest"])
    name = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[rest["day_of_week"] - 1]
    assert run(GET_MY_WORKOUT_DAY, users[0], DayArgs(day=name)) == {"day": name.capitalize(), "rest_day": True}


def test_no_workout_plan_says_where_to_make_one(client, users):
    onboard(client)
    assert run(GET_MY_WORKOUT_DAY, users[0]) == {"error": NO_WORKOUT_PLAN}


# ---------- today's log ----------

def test_todays_log_sums_what_was_logged_by_code(client, users):
    onboard(client)
    assert run(GET_TODAY_LOGGED, users[0])["meals_logged"] == 0
    logged = client.post("/meals", json={"slot": "lunch", "items": [
        {"food_id": food_id("roti"), "quantity": 2, "unit": "piece"}, {"food_id": food_id("sambar"), "quantity": 1, "unit": "katori"}]}).json()
    got = run(GET_TODAY_LOGGED, users[0])
    assert got["meals_logged"] == 1 and got["meals"][0]["slot"] == "lunch" and len(got["meals"][0]["foods"]) == 2
    assert "Roti" in got["meals"][0]["foods"][0] and "2 piece" in got["meals"][0]["foods"][0]
    assert got["totals_so_far"] == {k: round(logged["totals"][k], 1) for k in ("kcal", "protein_g", "carbs_g", "fat_g")}


# ---------- whose data ----------

def test_a_tool_only_ever_reads_the_callers_own_data(client, users, on_a_wednesday):
    onboard(client)
    approved_meal_plan(client)
    approved_workout_plan(client)
    client.post("/meals", json={"slot": "lunch", "items": [{"food_id": food_id("roti"), "quantity": 2, "unit": "piece"}]})
    other = users[1]                                                                           # never onboarded: has no data of their own
    assert run(GET_MY_TARGETS, other) == {"error": NO_TARGETS}
    assert run(GET_MY_MEAL_PLAN_DAY, other) == {"error": NO_MEAL_PLAN}
    assert run(GET_MY_WORKOUT_DAY, other) == {"error": NO_WORKOUT_PLAN}
    assert run(GET_TODAY_LOGGED, other)["meals_logged"] == 0
