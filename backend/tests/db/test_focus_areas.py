"""Focus areas against the real database: the endpoint, and what they do to a generated plan."""

import pytest

from app.db import admin_transaction
from app.llm.client import LLMBusy
from tests.db.test_onboarding_complete import FORMS, client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def model_is_down(monkeypatch):
    def down(user_id):
        def ask(prompt):
            raise LLMBusy()
        return ask
    monkeypatch.setattr("app.workflows.pick_exercises._default_ask", down)


def sets_by_key(payload):
    return {e["exercise_key"]: e["sets"] for d in payload["days"] for e in d["exercises"]}


def generate(client):
    with admin_transaction("test: let a new proposal be made") as conn:
        conn.execute("update public.plan_proposals set created_at = now() - interval '5 minutes' where user_id = %s",
                     (client.session.user_id,))
    return client.post("/plans/workout/generate").json()["payload"]


def onboard_gym(client, **screening):
    forms = {**FORMS, "training": {**FORMS["training"], "experience_level": "intermediate", "workout_location": "gym",
                                   "days_per_week": 3, "session_minutes": 60}}
    for step in ("consent", "basics", "goal", "preferences", "training"):
        assert client.put(f"/onboarding/{step}", json=forms[step]).status_code == 200
    assert client.put("/onboarding/screening", json={**forms["screening"], **screening}).status_code == 200
    assert client.post("/onboarding/complete").status_code == 200


def test_defaults_to_no_focus_and_lists_the_options(client):
    onboard(client)
    body = client.get("/training/focus-areas").json()
    assert body["focus_areas"] == [] and body["max_areas"] == 2
    assert {"chest", "glutes", "abs"} <= set(body["options"]) and "forearms" not in body["options"]


def test_save_and_read_back_and_clear(client):
    onboard(client)
    assert client.put("/training/focus-areas", json={"focus_areas": ["glutes", "chest", "glutes"]}).json()["focus_areas"] == ["glutes", "chest"]
    assert client.get("/training/focus-areas").json()["focus_areas"] == ["glutes", "chest"]
    assert client.put("/training/focus-areas", json={"focus_areas": []}).json()["focus_areas"] == []


@pytest.mark.parametrize("areas", [["chest", "back", "abs"], ["forearms"], ["full_body"], ["Chest"]])
def test_too_many_or_unknown_areas_are_refused_and_nothing_is_saved(client, areas):
    onboard(client)
    client.put("/training/focus-areas", json={"focus_areas": ["abs"]})
    assert client.put("/training/focus-areas", json={"focus_areas": areas}).status_code == 422
    assert client.get("/training/focus-areas").json()["focus_areas"] == ["abs"]


def test_each_person_has_their_own_focus(client, users):
    onboard(client)
    client.put("/training/focus-areas", json={"focus_areas": ["chest"]})
    client.session.user_id = users[1]
    assert client.get("/training/focus-areas").status_code == 404           # no profile yet: not someone else's answer
    client.session.user_id = users[0]
    assert client.get("/training/focus-areas").json()["focus_areas"] == ["chest"]


def test_the_database_itself_refuses_a_bad_focus_list(client, users):
    import psycopg
    onboard(client)
    for bad in (["chest", "back", "abs"], ["forearms"]):
        with pytest.raises(psycopg.errors.CheckViolation):
            with admin_transaction("test: bad focus straight into the table") as conn:
                conn.execute("update public.profiles set focus_areas = %s where id = %s", (bad, users[0]))


def test_a_focus_muscle_gets_more_sets_and_the_plan_says_so(client):
    onboard_gym(client)
    plain = generate(client)
    client.put("/training/focus-areas", json={"focus_areas": ["chest"]})
    boosted = generate(client)
    assert boosted["focus_areas"] == ["chest"] and boosted["focus_sets_added"] >= 1
    assert plain["focus_areas"] == [] and plain["focus_sets_added"] == 0
    base, more = sets_by_key(plain), sets_by_key(boosted)
    common = set(base) & set(more)
    assert common and all(more[k] >= base[k] for k in common)               # nothing lost a set
    assert any(more[k] > base[k] for k in common)                           # something gained one


def test_focus_days_get_one_more_exercise(client):
    onboard_gym(client)
    plain = generate(client)
    client.put("/training/focus-areas", json={"focus_areas": ["chest"]})
    boosted = generate(client)
    by_focus = lambda p: {d["focus"]: len(d["exercises"]) for d in p["days"] if not d["is_rest"]}
    before, after = by_focus(plain), by_focus(boosted)
    # The split is picked by the app (full body for 3 days, D-127), so days are not named Push/Pull: every day that trains chest gets exactly one more.
    assert before.keys() == after.keys() and all(after[k] in (before[k], before[k] + 1) for k in before)
    assert any(after[k] == before[k] + 1 for k in before)


def test_a_user_with_a_health_flag_gets_no_extra_volume_from_focus(client):
    onboard_gym(client, diabetes=True)
    client.put("/training/focus-areas", json={"focus_areas": ["chest"]})
    payload = generate(client)
    assert payload["focus_areas"] == [] and payload["focus_sets_added"] == 0 and payload["doctor_note"]
