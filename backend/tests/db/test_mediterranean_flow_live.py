"""Step 7.10e (D-094): the Mediterranean cuisine end to end against the real database, with the model switched off (code picks).

A user who chooses only Mediterranean gets a Mediterranean meal plan, the approval re-checks it against the cuisines saved TODAY, and the
saved plan is made of Mediterranean foods only. Needs `fooddata.load` to have been run after the migration."""

import pytest

from tests.db.test_meal_plan_flow import model_is_down, plans, q  # noqa: F401  (model_is_down is an autouse fixture)
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


def switch_to(client, cuisines):
    response = client.patch("/profile", json={"cuisines": cuisines})
    assert response.status_code == 200, response.text
    return response


def plan_cuisines(proposal):
    keys = sorted({i["food_key"] for d in proposal["payload"]["days"] for i in d["items"]})
    rows = q("select key, cuisines from public.foods where key = any(%s)", keys)
    return {k: set(c) for k, c in rows}, keys


def test_the_profile_accepts_a_list_of_cuisines_and_refuses_an_unknown_one(client, users):
    onboard(client)
    assert client.get("/profile").json()["cuisines"] == ["indian"]
    switch_to(client, ["mediterranean"])
    assert client.get("/profile").json()["cuisines"] == ["mediterranean"]
    switch_to(client, ["indian", "mediterranean"])
    assert client.get("/profile").json()["cuisines"] == ["indian", "mediterranean"]
    assert client.patch("/profile", json={"cuisines": ["martian"]}).status_code == 422
    assert client.patch("/profile", json={"cuisines": []}).status_code == 422
    assert client.patch("/profile", json={"cuisines": ["indian", "indian"]}).status_code == 422
    assert client.get("/profile").json()["cuisines"] == ["indian", "mediterranean"]        # the refused edits saved nothing


def test_a_mediterranean_only_user_gets_a_mediterranean_plan_and_it_can_be_approved(client, users):
    onboard(client)
    switch_to(client, ["mediterranean"])
    response = client.post("/plans/meal/generate")
    assert response.status_code == 200, response.text
    proposal = response.json()
    cuisines, keys = plan_cuisines(proposal)
    assert len(keys) >= 12 and all("mediterranean" in c for c in cuisines.values()), {k: c for k, c in cuisines.items() if "mediterranean" not in c}
    units = {i["unit"] for d in proposal["payload"]["days"] for i in d["items"]}
    assert "katori" not in units and {"bowl", "cup", "piece"} & units                                 # nothing Indian in the measures either
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200
    assert [p[0] for p in plans(users[0])] == ["active"]


def test_an_indian_only_user_never_gets_a_mediterranean_only_dish(client, users):
    onboard(client)
    proposal = client.post("/plans/meal/generate").json()
    cuisines, _ = plan_cuisines(proposal)
    assert all("indian" in c for c in cuisines.values()), {k: c for k, c in cuisines.items() if "indian" not in c}


def test_a_plan_made_for_one_cuisine_cannot_be_approved_after_the_user_switches_cuisine(client, users):
    """Approval re-verifies against the cuisines saved today (D-088), so a stale proposal cannot slip through."""
    onboard(client)
    proposal = client.post("/plans/meal/generate").json()                                              # made for Indian
    switch_to(client, ["mediterranean"])
    response = client.post(f"/plans/proposals/{proposal['id']}/approve")
    assert response.status_code in (409, 422), response.text
    assert plans(users[0]) == []                                                                       # nothing was applied


def test_changing_cuisines_makes_the_active_meal_plan_out_of_date(client, users):
    onboard(client)
    proposal = client.post("/plans/meal/generate").json()
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200
    body = switch_to(client, ["mediterranean"]).json()
    assert body["meal_plan_stale"] is True and body["workout_plan_stale"] is False
