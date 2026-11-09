"""Hand edits of the active workout plan through the API, against the real database (the model is off: code picks the exercises)."""

import pytest

from app.db import admin_transaction
from app.llm.client import LLMBusy
from tests.db.test_onboarding_complete import FORMS, client, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def model_is_down(monkeypatch):
    def down(user_id):
        def ask(prompt):
            raise LLMBusy()
        return ask
    monkeypatch.setattr("app.workflows.pick_exercises._default_ask", down)


def onboard_gym(client):
    forms = {**FORMS, "training": {**FORMS["training"], "experience_level": "intermediate", "workout_location": "gym",
                                   "days_per_week": 3, "session_minutes": 60}}
    for step in ("consent", "basics", "goal", "preferences", "training"):
        assert client.put(f"/onboarding/{step}", json=forms[step]).status_code == 200
    assert client.put("/onboarding/screening", json=forms["screening"]).status_code == 200
    assert client.post("/onboarding/complete").status_code == 200


@pytest.fixture
def plan(client):
    """An intermediate gym user with an APPROVED push/pull/legs plan (Mon, Wed, Fri)."""
    onboard_gym(client)
    client.put("/splits/choice", json={"split_key": "ppl_3"})
    proposal = client.post("/plans/workout/generate").json()
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200
    return client.get("/plans/workout/active").json()


def q(sql, *args):
    with admin_transaction("test: read") as conn:
        return conn.execute(sql, args).fetchall()


def day(plan, dow):
    return plan["days"][dow - 1]


def keys(plan, dow):
    return [e["exercise_key"] for e in day(plan, dow)["exercises"]]


def edit(client, body):
    return client.post("/plans/workout/edit", json=body)


def test_no_plan_means_no_edits_and_no_options(client):
    onboard_gym(client)
    response = edit(client, {"op": "move_day", "from_day": 1, "to_day": 2})
    assert response.status_code == 422 and "don't have a workout plan" in response.json()["detail"]
    assert client.get("/plans/workout/options", params={"day": 1}).status_code == 422


def test_moving_a_day_keeps_the_day_rows_so_logs_stay_linked(client, users, plan):
    ids_before = dict(q("select day_of_week, id from public.workout_plan_days where user_id = %s", users[0]))
    monday = keys(plan, 1)
    response = edit(client, {"op": "move_day", "from_day": 1, "to_day": 2})
    assert response.status_code == 200, response.text
    moved = response.json()
    assert moved["message"].startswith("Moved ") and "Monday to Tuesday" in moved["message"]
    assert keys(moved["plan"], 2) == monday and day(moved["plan"], 1)["is_rest"] and day(moved["plan"], 1)["exercises"] == []
    assert dict(q("select day_of_week, id from public.workout_plan_days where user_id = %s", users[0])) == ids_before      # same rows
    assert client.get("/plans/workout/active").json() == moved["plan"]                                                    # saved, not just shown
    assert q("select count(*), min(version) from public.workout_plans where user_id = %s", users[0])[0] == (1, 1)         # no new version


def test_swapping_a_day_with_another_training_day(client, plan):
    monday, wednesday = keys(plan, 1), keys(plan, 3)
    swapped = edit(client, {"op": "move_day", "from_day": 1, "to_day": 3}).json()["plan"]
    assert keys(swapped, 1) == wednesday and keys(swapped, 3) == monday
    assert edit(client, {"op": "move_day", "from_day": 2, "to_day": 4}).status_code == 422      # Tuesday is a rest day


def test_swap_remove_and_add_use_the_options_the_server_offers(client, plan):
    before = keys(plan, 1)
    options = client.get("/plans/workout/options", params={"day": 1, "position": 1}).json()["options"]
    assert options and all(o["key"] not in before for o in options)
    pick = options[0]["key"]
    swapped = edit(client, {"op": "swap_exercise", "day": 1, "position": 1, "exercise_key": pick})
    assert swapped.status_code == 200, swapped.text
    after = swapped.json()["plan"]
    assert keys(after, 1)[0] == pick and keys(after, 1)[1:] == before[1:]                       # only that exercise changed
    first = day(after, 1)["exercises"][0]
    assert first["sets"] >= 2 and first["reps_min"] >= 1 and first["rest_sec"] > 0 and first["form_cues"]
    assert keys(after, 3) == keys(plan, 3)                                                      # other days untouched

    removed = edit(client, {"op": "remove_exercise", "day": 1, "position": 2}).json()["plan"]
    assert len(keys(removed, 1)) == len(before) - 1 and [e["position"] for e in day(removed, 1)["exercises"]] == list(range(1, len(before)))

    addable = client.get("/plans/workout/options", params={"day": 1}).json()["options"]
    assert addable
    added = edit(client, {"op": "add_exercise", "day": 1, "exercise_key": addable[0]["key"]}).json()["plan"]
    assert keys(added, 1)[-1] == addable[0]["key"] and len(keys(added, 1)) == len(before)


def test_an_exercise_that_hurts_a_reported_injury_is_never_offered_or_accepted(client, users, plan):
    knee = [r[0] for r in q("select key from public.exercises where 'knee' = any(contraindications) and difficulty <> 'advanced'")]
    assert knee
    with admin_transaction("test: report a knee injury after the plan was made") as conn:
        conn.execute("update public.health_screening set injury_areas = %s where user_id = %s", (["knee"], users[0]))
    for dow in (1, 3, 5):
        offered = {o["key"] for o in client.get("/plans/workout/options", params={"day": dow}).json()["options"]}
        assert offered and not offered & set(knee)
    response = edit(client, {"op": "add_exercise", "day": 5, "exercise_key": knee[0]})
    assert response.status_code == 422 and "could aggravate your knee" in response.json()["detail"]
    assert keys(client.get("/plans/workout/active").json(), 5) == keys(plan, 5)                  # nothing was written


def test_bad_requests_are_refused_by_the_same_field_rules_as_everywhere(client, plan):
    assert edit(client, {"op": "teleport"}).status_code == 422
    assert edit(client, {"op": "move_day", "from_day": 1, "to_day": 9}).status_code == 422
    assert edit(client, {"op": "move_day", "from_day": 1, "to_day": 2, "extra": 1}).status_code == 422
    assert edit(client, {"op": "add_exercise", "day": 1, "exercise_key": "Not A Key!"}).status_code == 422
    assert edit(client, {"op": "add_exercise", "day": 1, "exercise_key": "moon_press"}).json()["detail"] == "That exercise is not in our library."
    assert edit(client, {"op": "move_day", "from_day": 1, "to_day": 1}).json()["detail"] == "That is already the day."
    assert client.get("/plans/workout/active").json() == plan                                    # nothing changed


def test_nobody_edits_or_sees_someone_elses_plan(client, users, plan):
    client.session.user_id = users[1]
    response = edit(client, {"op": "move_day", "from_day": 1, "to_day": 2})
    assert response.status_code == 422                                                           # they have no plan (and not onboarded)
    client.session.user_id = users[0]
    assert client.get("/plans/workout/active").json() == plan


def test_an_archived_plan_cannot_be_edited_only_the_active_one(client, users, plan):
    second = client.post("/plans/workout/generate")
    assert second.status_code == 200
    with admin_transaction("test: age the first proposal so a new one is made") as conn:
        conn.execute("update public.plan_proposals set created_at = now() - interval '5 minutes' where user_id = %s", (users[0],))
    newer = client.post("/plans/workout/generate").json()
    assert client.post(f"/plans/proposals/{newer['id']}/approve").status_code == 200            # the first plan is archived now
    moved = edit(client, {"op": "move_day", "from_day": 1, "to_day": 2}).json()["plan"]
    archived = q("select count(*) from public.workout_plan_exercises e join public.workout_plan_days d on d.id = e.plan_day_id "
                 "join public.workout_plans p on p.id = d.workout_plan_id where p.user_id = %s and p.status = 'archived'", users[0])[0][0]
    assert archived > 0 and moved["id"] != plan["id"]                                            # the old plan keeps its exercises
    assert keys(moved, 2) != []
