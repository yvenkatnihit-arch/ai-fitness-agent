"""Check that the whole demo works for a BRAND-NEW account, in about a minute (Step 8.14, D-117).

Run from backend/:
    uv run python scripts/demo_check.py             # the whole journey, plans made by code (free, no Gemini)
    uv run python scripts/demo_check.py --chat      # also asks 4 real questions in the chat and logs a meal (real Gemini, about a cent)

It creates a throwaway user in the real database, goes through onboarding, targets, meal and workout plans with their approvals, a logged meal, the
dashboard, weight entries with a trend, "How the AI works", and (with --chat) the chat; prints PASS or FAIL for each step, and deletes the user.
It does NOT test sign-up or sign-in themselves (those are Supabase's, and the user here is created directly): try a sign-up with a new email yourself.
Exit code 1 when a step fails."""

import sys
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CHAT = "--chat" in sys.argv


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def step(self, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((ok, name, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)
        return ok

    @property
    def failed(self) -> int:
        return sum(not ok for ok, _, _ in self.rows)


def main() -> int:
    import app.core.chat_limits as limits
    import app.workflows.pick_exercises as pick_exercises
    import app.workflows.pick_meals as pick_meals
    from fastapi.testclient import TestClient

    from app.core.auth import CurrentUser, get_current_user
    from app.core.time import india_today
    from app.db import admin_transaction, close_pool, ping
    from app.llm.client import LLMBusy
    from app.main import app
    from tests.db.test_onboarding_complete import FORMS

    r = Report()
    print("Demo check: a brand-new account, start to finish" + (" (with the real chat)" if CHAT else " (no Gemini)"))
    r.step("the database is reachable", bool(ping()))

    def down(user_id):
        def ask(prompt):
            raise LLMBusy()
        return ask

    pick_meals._default_ask = pick_exercises._default_ask = down       # plans are made by code: this run costs nothing
    limits.WINDOWS = ((600, 10_000), (86_400, 100_000))                 # this process only
    uid = uuid.uuid4()
    with admin_transaction("demo check: scratch user") as c:
        c.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"scratch-{uid}@example.test"))
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uid, email=None)
    try:
        with TestClient(app) as client:
            ok = lambda response: response.status_code == 200      # noqa: E731
            r.step("a new account is sent to onboarding", client.get("/onboarding/status").json().get("next_step") == "consent")
            forms = {**FORMS, "goal": {**FORMS["goal"], "pace": "normal"}}
            all_ok = all(ok(client.put(f"/onboarding/{s}", json=forms[s])) for s in ("consent", "basics", "goal", "preferences", "training", "screening"))
            r.step("the six onboarding forms save", all_ok)
            done = client.post("/onboarding/complete")
            body = done.json() if ok(done) else {}
            r.step("onboarding finishes with daily targets", ok(done) and body.get("calorie_target_kcal", 0) > 1000, f"{body.get('calorie_target_kcal')} kcal, {body.get('protein_g')} g protein")
            home = client.get("/targets/current")
            r.step("Home can read the targets", ok(home) and home.json()["calorie_target_kcal"] == body.get("calorie_target_kcal"))
            r.step("the goal-date forecast works", ok(client.get("/targets/forecast")))

            meal = client.post("/plans/meal/generate")
            r.step("a meal plan is proposed (not saved yet)", ok(meal) and len(meal.json()["payload"]["days"]) == 7)
            before = client.get("/plans/meal/active").status_code
            approved = client.post(f"/plans/proposals/{meal.json()['id']}/approve") if ok(meal) else None
            active = client.get("/plans/meal/active")
            r.step("approving it makes it the active plan (and only then)", before == 404 and approved is not None and ok(approved) and ok(active) and len(active.json()["days"]) == 7)

            workout = client.post("/plans/workout/generate")
            approved = client.post(f"/plans/proposals/{workout.json()['id']}/approve") if ok(workout) else None
            r.step("a workout plan is proposed and approved", ok(workout) and approved is not None and ok(approved) and ok(client.get("/plans/workout/active")))

            with admin_transaction("demo check: a food id") as c:
                roti = c.execute("select id from public.foods where key = 'roti'").fetchone()[0]
            logged = client.post("/meals", json={"slot": "lunch", "items": [{"food_id": roti, "quantity": 2, "unit": "piece"}]})
            r.step("a meal can be logged", logged.status_code == 201, f"{logged.json().get('totals', {}).get('kcal')} kcal" if logged.status_code == 201 else "")
            today = client.get("/dashboard/today")
            t = today.json() if ok(today) else {}
            r.step("the dashboard shows what was eaten against the target", bool(t) and t["progress"]["kcal"]["eaten"] > 0 and bool(t["meal_plan"]) is not None, f"{t.get('progress', {}).get('kcal', {}).get('percent')}% of calories")

            for n, kg in ((10, 59.5), (6, 58.8), (3, 58.0)):
                client.post("/weight", json={"weight_kg": kg, "measured_on": (india_today() - timedelta(days=n)).isoformat()})
            weight = client.post("/weight", json={"weight_kg": 57.2})
            w = weight.json() if ok(weight) else {}
            r.step("weigh-ins build a trend", ok(weight) and len(w["entries"]) >= 4 and w["weekly_change_kg"] is not None, f"{len(w.get('entries', []))} points, {w.get('weekly_change_kg')} kg a week")
            r.step("the targets did not change with the weigh-ins", client.get("/targets/current").json() == home.json())
            insights = client.get("/insights/ai")
            r.step("the 'How the AI works' page has rules, scores and usage", ok(insights) and len(insights.json()["rules"]) >= 6 and len(insights.json()["quality"]["evals"]) >= 5)
            override = app.dependency_overrides.pop(get_current_user)            # take the test login away for a moment: a stranger must be refused
            try:
                with TestClient(app) as stranger:
                    refused = [stranger.get(p).status_code for p in ("/targets/current", "/dashboard/today", "/weight", "/chat", "/insights/ai")]
                    refused.append(stranger.post("/chat", json={"message": "hi"}).status_code)
            finally:
                app.dependency_overrides[get_current_user] = override
            r.step("a visitor with no login is refused everywhere (security)", all(code in (401, 403) for code in refused), str(refused))

            if CHAT:
                def ask(q, cid=None):
                    res = client.post("/chat", json={"message": q, **({"conversation_id": cid} if cid else {})})
                    return (res.json() if ok(res) else {"reply": f"HTTP {res.status_code}", "meta": {"specialists": []}, "waiting_for": None, "conversation_id": cid})
                a = ask("how much protein is in paneer")
                r.step("chat: a food question is answered from our data", "26" in a["reply"] and a["meta"]["specialists"][0]["name"] == "nutrition", a["reply"][:70])
                b = ask("what is my calorie target")
                r.step("chat: it knows your own targets", str(body.get("calorie_target_kcal")) in b["reply"], b["reply"][:70])
                c2 = ask("what workout do I have on friday")
                r.step("chat: it knows your workout plan", c2["meta"]["specialists"] and c2["meta"]["specialists"][0]["name"] == "my_plan", c2["reply"][:70])
                d = ask("I ate 2 rotis and dal for lunch")
                r.step("chat: logging a meal prepares a card and saves nothing yet", bool(d["waiting_for"]) and len(client.get("/meals").json()["meals"]) == 1)
                if d["waiting_for"]:
                    decided = client.post(f"/chat/{d['conversation_id']}/decide", json={"choice": "approve"})
                    r.step("chat: approving the card logs the meal", ok(decided) and len(client.get("/meals").json()["meals"]) == 2)
    finally:
        app.dependency_overrides.clear()
        with admin_transaction("demo check: cleanup") as c:
            c.execute("delete from auth.users where id = %s", (uid,))
        close_pool()
    print(f"\n{len(r.rows) - r.failed} of {len(r.rows)} steps passed." + ("" if not r.failed else f" {r.failed} FAILED: see above."))
    return 1 if r.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
