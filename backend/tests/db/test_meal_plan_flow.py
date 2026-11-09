"""Meal plans end to end against the real database, with the model switched off (the code fallback picks the dishes)."""

import json
import uuid

import pytest

from app.db import admin_transaction
from app.llm.client import LLMBusy
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def model_is_down(monkeypatch):
    def down(user_id):
        def ask(prompt):
            raise LLMBusy()
        return ask
    monkeypatch.setattr("app.workflows.pick_meals._default_ask", down)


@pytest.fixture
def proposal(client):
    onboard(client)
    response = client.post("/plans/meal/generate")
    assert response.status_code == 200, response.text
    return response.json()


def q(sql, *args):
    with admin_transaction("test: read") as conn:
        return conn.execute(sql, args).fetchall()


def plans(user_id):
    return q("select status, version, week_start, targets_id is not null from public.meal_plans where user_id = %s order by created_at", user_id)


def pid(proposal):
    return uuid.UUID(proposal["id"])


def test_nothing_to_generate_before_onboarding(client):
    response = client.post("/plans/meal/generate")
    assert response.status_code == 409 and "finish onboarding" in response.json()["detail"]


def test_generate_makes_a_pending_proposal_and_no_plan(client, users, proposal):
    assert proposal["type"] == "meal_change" and proposal["source"] == "plan_generation" and proposal["status"] == "pending"
    assert proposal["summary"].startswith("7-day vegetarian meal plan, 4 meals a day, about ")
    payload = proposal["payload"]
    assert [d["day_of_week"] for d in payload["days"]] == list(range(1, 8)) and payload["numbers_hidden"] is False
    assert plans(users[0]) == []                                    # a proposal is not a plan


def test_approve_writes_the_plan_with_code_computed_numbers(client, users, proposal):
    response = client.post(f"/plans/proposals/{proposal['id']}/approve")
    assert response.status_code == 200 and response.json()["status"] == "approved"
    [(status, version, week_start, has_targets)] = plans(users[0])
    assert (status, version, has_targets) == ("active", 1, True) and week_start.weekday() == 0
    stored = q("""select i.day_of_week, i.slot, i.position, f.key, i.grams, i.household_unit, i.household_qty,
                         i.kcal, i.protein_g, f.kcal_per_100g
                  from public.meal_plan_items i join public.foods f on f.id = i.food_id
                  where i.user_id = %s order by i.day_of_week, i.slot, i.position""", users[0])
    shown = [i for d in proposal["payload"]["days"] for i in d["items"]]
    assert len(stored) == len(shown) > 40
    for row, item in zip(sorted(stored, key=lambda r: (r[0], r[1], r[2])), sorted(
            ((d["day_of_week"], i) for d in proposal["payload"]["days"] for i in d["items"]),
            key=lambda x: (x[0], x[1]["slot"], x[1]["position"]))):
        day, it = item
        assert (row[0], row[1], row[2], row[3]) == (day, it["slot"], it["position"], it["food_key"])
        assert float(row[4]) == it["grams"]
        assert float(row[7]) == pytest.approx(round(it["grams"] * float(row[9]) / 100, 1), abs=0.11)     # recomputed from the food, not copied
    [(decided,)] = q("select decided_at is not null from public.plan_proposals where id = %s", pid(proposal))
    assert decided


def test_every_day_of_the_saved_plan_is_inside_the_safe_calorie_band(client, users, proposal):
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    target = proposal["payload"]["targets"]["kcal"]
    for day, kcal in q("select day_of_week, sum(kcal) from public.meal_plan_items where user_id = %s group by 1 order by 1", users[0]):
        assert target * 0.9 <= float(kcal) <= target * 1.1, (day, kcal, target)


def test_approving_twice_makes_no_second_plan(client, users, proposal):
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 200
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 409
    assert len(plans(users[0])) == 1


def test_a_tampered_portion_is_refused_and_nothing_is_written(client, users, proposal):
    with admin_transaction("test: inflate a portion in the stored plan") as conn:
        conn.execute("update public.plan_proposals set payload = jsonb_set(payload, '{days,0,items,0,grams}', '1500') where id = %s",
                     (pid(proposal),))
    response = client.post(f"/plans/proposals/{proposal['id']}/approve")
    assert response.status_code == 422 and "safety checks" in response.json()["detail"]
    assert plans(users[0]) == []
    assert q("select count(*) from public.meal_plan_items where user_id = %s", users[0])[0][0] == 0
    assert q("select status from public.plan_proposals where id = %s", pid(proposal))[0][0] == "pending"


def test_a_food_the_diet_forbids_is_refused(client, users, proposal):
    with admin_transaction("test: swap in a chicken dish for a vegetarian") as conn:
        conn.execute("update public.plan_proposals set payload = jsonb_set(payload, '{days,0,items,0,food_key}', '\"chicken_biryani\"')"
                     " where id = %s", (pid(proposal),))
    response = client.post(f"/plans/proposals/{proposal['id']}/approve")
    assert response.status_code == 422 and plans(users[0]) == []


def test_an_invented_food_is_refused(client, users, proposal):
    with admin_transaction("test: invent a food in the stored plan") as conn:
        conn.execute("update public.plan_proposals set payload = jsonb_set(payload, '{days,2,items,1,food_key}', '\"moon_cheese\"')"
                     " where id = %s", (pid(proposal),))
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 422
    assert plans(users[0]) == []


def test_nobody_can_decide_someone_elses_meal_plan(client, users, proposal):
    client.session.user_id = users[1]
    assert client.post(f"/plans/proposals/{proposal['id']}/approve").status_code == 404
    assert client.post(f"/plans/proposals/{proposal['id']}/reject").status_code == 404
    assert plans(users[0]) == [] and plans(users[1]) == []
    assert q("select status from public.plan_proposals where id = %s", pid(proposal))[0][0] == "pending"


def test_reject_changes_nothing_else(client, users, proposal):
    assert client.post(f"/plans/proposals/{proposal['id']}/reject").json()["status"] == "rejected"
    assert plans(users[0]) == []


def test_a_double_tap_reuses_the_proposal_and_a_later_one_replaces_it(client, users, proposal):
    again = client.post("/plans/meal/generate").json()
    assert again["id"] == proposal["id"]
    with admin_transaction("test: make the proposal look old") as conn:
        conn.execute("update public.plan_proposals set created_at = now() - interval '5 minutes' where user_id = %s", (users[0],))
    newer = client.post("/plans/meal/generate").json()
    assert newer["id"] != proposal["id"]
    assert q("select status from public.plan_proposals where id = %s", pid(proposal))[0][0] == "expired"
    pending = [p["id"] for p in client.get("/plans/proposals/pending").json()["proposals"] if p["type"] == "meal_change"]
    assert pending == [newer["id"]]


def test_a_second_approval_archives_the_first_plan(client, users, proposal):
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    second = client.post("/plans/meal/generate").json()
    assert second["id"] != proposal["id"]
    assert client.post(f"/plans/proposals/{second['id']}/approve").status_code == 200
    assert [(r[0], r[1]) for r in plans(users[0])] == [("archived", 1), ("active", 2)]
    assert q("select count(distinct meal_plan_id) from public.meal_plan_items where user_id = %s", users[0])[0][0] == 2


def test_a_workout_and_a_meal_proposal_can_wait_side_by_side(client, users, proposal):
    pending = client.get("/plans/proposals/pending").json()["proposals"]
    assert [p["type"] for p in pending] == ["meal_change"]


def test_dislikes_are_respected(client, users):
    onboard(client)
    with admin_transaction("test: set dislikes") as conn:
        conn.execute("update public.profiles set disliked_foods = %s where id = %s", (["paneer", "rajma", "palak"], users[0]))
    payload = client.post("/plans/meal/generate").json()["payload"]
    names = {i["name"].casefold() for d in payload["days"] for i in d["items"]}
    assert names and not any(w in n for n in names for w in ("paneer", "rajma", "palak"))


def test_eating_disorder_history_never_sees_calories_or_macros(client, users):
    onboard(client, eating_disorder_history=True)
    response = client.post("/plans/meal/generate")
    assert response.status_code == 200, response.text
    body = response.json()
    text = json.dumps(body)
    assert body["payload"]["numbers_hidden"] is True and "kcal" not in text
    plan_text = json.dumps(body["payload"])                      # the plan itself (the proposal wrapper has its own status)
    for key in ("kcal", "protein_g", "carbs_g", "fat_g", "targets", "totals", "percent_of_target", "issues", "status", "emphasis", "portion_scale"):
        assert f'"{key}"' not in plan_text, key
    assert "issues" not in plan_text and "high_protein" not in plan_text
    assert body["payload"]["days"][0]["items"][0]["grams"] > 0                    # portions are still shown
    pending = json.dumps(client.get("/plans/proposals/pending").json())
    assert "kcal" not in pending and '"protein_g"' not in pending
    # the numbers still exist on our side (the plan tables need them, and the safety check needs them)
    assert q("select payload -> 'days' -> 0 -> 'items' -> 0 -> 'kcal' from public.plan_proposals where id = %s", pid(body))[0][0] is not None
    assert client.post(f"/plans/proposals/{body['id']}/approve").status_code == 200
    assert q("select min(kcal) from public.meal_plan_items where user_id = %s", users[0])[0][0] > 0


def test_a_user_without_hidden_numbers_gets_them(client, users, proposal):
    day = proposal["payload"]["days"][0]
    assert day["totals"]["kcal"] > 0 and day["items"][0]["kcal"] > 0 and proposal["payload"]["targets"]["kcal"] > 0


def test_a_junk_meal_payload_is_refused_not_silently_approved(client, users):
    from psycopg.types.json import Jsonb
    onboard(client)
    with admin_transaction("test: insert a junk meal proposal") as conn:
        junk = conn.execute(
            "insert into public.plan_proposals (user_id, type, source, summary, payload) values (%s, 'meal_change', 'chat', 'x', %s) returning id",
            (users[0], Jsonb({"kind": "meal_plan"}))).fetchone()[0]
    response = client.post(f"/plans/proposals/{junk}/approve")
    assert response.status_code == 422 and "safety checks" in response.json()["detail"]
    assert plans(users[0]) == [] and q("select status from public.plan_proposals where id = %s", junk)[0][0] == "pending"


# --- the active plan (what the screen reads) ---

def test_there_is_no_active_meal_plan_until_one_is_approved(client, proposal):
    assert client.get("/plans/meal/active").status_code == 404           # a proposal is not a plan


def test_the_active_plan_matches_what_was_approved(client, users, proposal):
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    view = client.get("/plans/meal/active").json()
    assert view["version"] == 1 and view["numbers_hidden"] is False and [d["day_of_week"] for d in view["days"]] == list(range(1, 8))
    shown = [i["food_key"] for d in proposal["payload"]["days"] for i in d["items"]]
    assert sum(len(m["items"]) for d in view["days"] for m in d["meals"]) == len(shown)
    for day in view["days"]:
        assert [m["slot"] for m in day["meals"]] == ["breakfast", "lunch", "evening_snack", "dinner"]
        assert day["totals"]["kcal"] == pytest.approx(sum(i["kcal"] for m in day["meals"] for i in m["items"]), abs=0.2)
    assert view["targets"] == proposal["payload"]["targets"]
    assert all(i["text"] and i["grams"] > 0 for d in view["days"] for m in d["meals"] for i in m["items"])


def test_the_active_plan_carries_the_how_this_was_made_summary(client, proposal):
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    made = client.get("/plans/meal/active").json()["how_made"]
    assert made["days_from_model"] + made["days_from_code"] == 7 and made["sources"] == ["fallback"] * 7     # the model is down here
    assert made["generation"] is None and made["checks"] and made["meals_per_day"] == 4
    assert "average_percent_of_target" in made and "days_ok" in made
    assert made == proposal["payload"]["how_made"]                                                          # same summary the user saw


def test_nobody_reads_someone_elses_meal_plan(client, users, proposal):
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    client.session.user_id = users[1]
    assert client.get("/plans/meal/active").status_code == 404


def test_the_active_plan_follows_the_latest_approval(client, users, proposal):
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    first = client.get("/plans/meal/active").json()["id"]
    response = client.post("/plans/meal/generate")
    assert response.status_code == 200, response.text
    second = response.json()
    client.post(f"/plans/proposals/{second['id']}/approve")
    view = client.get("/plans/meal/active").json()
    assert view["id"] != first and view["version"] == 2


def test_eating_disorder_history_gets_no_numbers_from_the_active_plan_either(client, users):
    onboard(client, eating_disorder_history=True)
    proposal = client.post("/plans/meal/generate").json()
    assert "how_made" in proposal["payload"] and "days_ok" not in proposal["payload"]["how_made"]
    client.post(f"/plans/proposals/{proposal['id']}/approve")
    text = json.dumps(client.get("/plans/meal/active").json())
    assert '"numbers_hidden": true' in text and '"targets": null' in text and '"totals": null' in text
    for key in ("days_ok", "days_with_issues", "average_percent_of_target", "emphasis", "portion_scale"):
        assert f'"{key}"' not in text, key
    assert '"kcal": null' in text and '"protein_g": null' in text and '"fat_g": null' in text
    assert '"text": "' in text                                                    # portions are still shown
