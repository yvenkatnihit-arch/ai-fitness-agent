"""Evaluate the exercise, meal-logging and my-plan specialists end to end with REAL Gemini calls (Step 8.9, D-115).

A scratch user is created in the real database with a real onboarding, approved meal and workout plans (made by code, no model), a logged
meal and two weigh-ins; the questions go through the real chat endpoint (router, specialist, guards, claims rule); the answers are scored against
what the app itself says is true. Nothing is cached: the answers depend on the database, so every run asks again (about 20 questions, a few cents).
The scratch user is deleted at the end."""

import statistics
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from evals.specialist_cases import CASES, Answer, Case, Truth

MAX_QUESTIONS = 40


@dataclass(frozen=True)
class CaseResult:
    name: str
    specialist: str
    question: str
    reply: str
    tools: tuple[str, ...]
    reason: str | None           # None = passed
    latency_s: float

    @property
    def passed(self) -> bool:
        return self.reason is None


def score(case: Case, answer: Answer, truth: Truth, latency_s: float = 0.0) -> CaseResult:
    return CaseResult(case.name, case.specialist, case.question, answer.reply, tuple(answer.tools), case.check(answer, truth), latency_s)


def summarize(results: list[CaseResult]) -> dict:
    n = len(results) or 1
    out = {"cases": len(results), "pass_rate": sum(r.passed for r in results) / n,
           "median_latency_s": statistics.median(r.latency_s for r in results) if results else 0.0}
    for who in ("exercises", "meal_logger", "my_plan"):
        mine = [r for r in results if r.specialist == who]
        out[f"{who}_pass_rate"] = sum(r.passed for r in mine) / len(mine) if mine else 1.0
    return out


def build_truth(client, user_id) -> Truth:
    """What is TRUE about the test user, from the app's own endpoints and the exercise library."""
    from app.db import user_transaction
    from app.db import exercises as repo
    from app.calc.exercise_search import words  # noqa: F401  (kept so a rename here fails loudly)

    targets = client.get("/targets/current").json()
    weight = client.get("/weight").json()
    meal = client.get("/plans/meal/active").json()
    workout = client.get("/plans/workout/active").json()
    today = client.get("/dashboard/today").json()
    dinner = next(d for d in meal["days"] if d["day_of_week"] == 3)
    dinner_items = next((m["items"] for m in dinner["meals"] if m["slot"] == "dinner"), [])
    friday = next(d for d in workout["days"] if d["day_of_week"] == 5)
    with user_transaction(user_id) as conn:
        options = repo.list_exercises(conn)
    library = {o.name.lower(): tuple(o.contraindications) for o in options}
    return Truth(targets=targets, weight=weight, wednesday_dinner=[i["name"] for i in dinner_items],
                 friday_workout=[e["name"] for e in friday["exercises"]], eaten_today_kcal=(today["progress"]["kcal"]["eaten"] if today.get("progress") else 0.0),
                 library=library, plain_names=set(library))


def run_specialist_eval(*, ask: Callable | None = None, only: list[str] | None = None) -> list[CaseResult]:
    """Real run. `ask(client, question) -> Answer` is replaceable in tests; production asks the real chat endpoint."""
    import time

    import app.core.chat_limits as limits
    import app.workflows.pick_exercises as pe
    import app.workflows.pick_meals as pm
    from fastapi.testclient import TestClient

    from app.core.auth import CurrentUser, get_current_user
    from app.core.time import india_today
    from app.db import admin_transaction, close_pool
    from app.llm.client import LLMBusy
    from app.main import app
    from tests.db.test_onboarding_complete import FORMS

    cases = [c for c in CASES if only is None or c.specialist in only]
    if len(cases) > MAX_QUESTIONS:
        raise RuntimeError(f"eval budget reached: {len(cases)} questions (cap {MAX_QUESTIONS})")

    def down(user_id):
        def raise_busy(prompt):
            raise LLMBusy()
        return raise_busy

    saved = (limits.WINDOWS, pe._default_ask, pm._default_ask)
    limits.WINDOWS = ((600, 10_000), (86_400, 100_000))          # this process only: the eval asks more than a person would
    pe._default_ask = pm._default_ask = down                      # the plans are made by code, so the eval measures the CHAT, not plan generation
    uid = uuid.uuid4()
    with admin_transaction("specialist eval: scratch user") as c:
        c.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"scratch-{uid}@example.test"))
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uid, email=None)
    results: list[CaseResult] = []
    try:
        with TestClient(app) as client:
            forms = {**FORMS, "goal": {**FORMS["goal"], "pace": "normal"}}
            for step in ("consent", "basics", "goal", "preferences", "training", "screening"):
                client.put(f"/onboarding/{step}", json=forms[step])
            client.post("/onboarding/complete")
            client.put("/splits/choice", json={"split_key": "full_body_3"})
            for kind in ("meal", "workout"):
                proposal = client.post(f"/plans/{kind}/generate").json()
                client.post(f"/plans/proposals/{proposal['id']}/approve")
            with admin_transaction("specialist eval: a food id") as c:
                roti = c.execute("select id from public.foods where key = 'roti'").fetchone()[0]
            client.post("/meals", json={"slot": "breakfast", "items": [{"food_id": roti, "quantity": 2, "unit": "piece"}]})
            client.post("/weight", json={"weight_kg": 59.5, "measured_on": (india_today() - timedelta(days=10)).isoformat()})
            client.post("/weight", json={"weight_kg": 57.0})
            truth = build_truth(client, uid)

            def real_ask(c, question: str) -> Answer:
                body = c.post("/chat", json={"message": question}).json()
                specialists = body.get("meta", {}).get("specialists", [])
                return Answer(body.get("reply", ""), (body.get("waiting_for") or {}).get("summary"),
                              [t for s in specialists for t in s["tools"]], body.get("blocked"))

            for case in cases:
                started = time.monotonic()
                answer = (ask or real_ask)(client, case.question)
                results.append(score(case, answer, truth, time.monotonic() - started))
    finally:
        app.dependency_overrides.clear()
        limits.WINDOWS, pe._default_ask, pm._default_ask = saved
        with admin_transaction("specialist eval: cleanup") as c:
            c.execute("delete from auth.users where id = %s", (uid,))
        close_pool()
    return results
