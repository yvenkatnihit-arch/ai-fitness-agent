"""Step 7.7b: the router eval HARNESS, tested with a fake model (no real calls, free). The real run is `python -m evals.run_llm router`."""

import json

import pytest

from app.agents.menu import default_menu
from evals import router_eval, run_llm
from evals.router_cases import CASES
from app.llm.client import LLMResult


@pytest.fixture(autouse=True)
def private_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(router_eval, "CACHE", tmp_path / "cache" / "router.json")


def fake(answers: dict[str, str], default='{"assignments": []}'):
    calls = []

    def call(tier, messages, **kw):
        calls.append(kw)
        message = messages[1][1]
        return LLMResult(answers.get(message, default), "fake", 100, 20, 0, 0.0001, 7)
    call.calls = calls   # type: ignore[attr-defined]
    return call


NUTRITION = '{"assignments": [{"specialist": "nutrition", "task": "q"}]}'
TWO_CASES = [("protein in paneer?", ("nutrition",), ()), ("hello", (), ()), ("what to eat today", ("nutrition",), ("borderline",))]


# ---------- the dataset ----------

def test_the_dataset_is_well_formed():
    names = set(default_menu())
    assert len({m for m, _, _ in CASES}) == len(CASES)
    assert all(set(expected) <= names for _, expected, _ in CASES)
    scored = [c for c in CASES if "borderline" not in c[2]]
    assert len(scored) >= 30 and any(e for _, e, _ in scored) and any(not e for _, e, _ in scored)


# ---------- raw checks ----------

@pytest.mark.parametrize("text, expected", [
    (NUTRITION, (True, (), False)),
    ('{"assignments": []}', (True, (), False)),
    ('```json\n{"assignments": []}\n```', (True, (), False)),
    ('{"assignments": [{"specialist": "hacker", "task": "x"}]}', (True, ("hacker",), False)),
    ('{"assignments": [{"specialist": "nutrition", "task": "a"}, {"specialist": "nutrition", "task": "b"}]}', (True, (), True)),
    ("not json", (False, (), False)), ('{"other": 1}', (False, (), False)), ('{"assignments": 5}', (False, (), False)),
])
def test_raw_checks_look_at_the_models_own_reply(text, expected):
    assert router_eval.raw_checks(text, {"nutrition"}) == expected


# ---------- running ----------

def test_a_run_scores_each_case_and_summarises():
    call = fake({"protein in paneer?": NUTRITION, "what to eat today": NUTRITION})
    results = router_eval.run_router_eval(call, cases=TWO_CASES)
    assert [r.passed for r in results] == [True, True, True]
    s = router_eval.summarize(results)
    assert (s["cases"], s["scored"], s["borderline"]) == (3, 2, 1)
    assert s["exact_accuracy"] == s["nutrition_recall"] == s["off_topic_specificity"] == 1.0
    assert s["avg_tokens"] == 120 and s["total_cost_usd"] == pytest.approx(0.0003)
    assert all(kw["flow"] == "eval" and kw["node"] == "router" and kw["max_tokens"] == 200 and kw["temperature"] == 0.0 for kw in call.calls)


def test_wrong_answers_lower_the_scores():
    call = fake({"hello": NUTRITION})                       # routes a greeting to nutrition, misses the food question
    results = router_eval.run_router_eval(call, cases=TWO_CASES)
    s = router_eval.summarize(results)
    assert [r.passed for r in results] == [False, False, True]
    assert s["exact_accuracy"] == 0.0 and s["nutrition_recall"] == 0.0 and s["off_topic_specificity"] == 0.0


def test_a_borderline_case_accepts_either_answer_but_never_an_off_menu_one():
    case = [("what to eat today", ("nutrition",), ("borderline",))]
    assert router_eval.run_router_eval(fake({}), cases=case)[0].passed                                # [] is acceptable
    assert router_eval.run_router_eval(fake({"what to eat today": NUTRITION}), cases=case, use_cache=False)[0].passed
    off = fake({"what to eat today": '{"assignments": [{"specialist": "hacker", "task": "x"}]}'})
    r = router_eval.run_router_eval(off, cases=case, use_cache=False)[0]
    assert r.got == () and r.off_menu == ("hacker",)                                                   # validated away, but counted


def test_the_models_raw_mistakes_are_counted_even_though_validation_hides_them():
    bad = fake({"hello": "not json", "protein in paneer?": '{"assignments": [{"specialist": "hacker", "task": "x"}]}'})
    s = router_eval.summarize(router_eval.run_router_eval(bad, cases=TWO_CASES))
    assert s["invalid_json_rate"] == pytest.approx(1 / 3) and s["off_menu_rate"] == pytest.approx(1 / 3)


def test_the_cache_means_a_second_run_makes_no_calls():
    first = fake({"protein in paneer?": NUTRITION})
    router_eval.run_router_eval(first, cases=TWO_CASES)
    assert len(first.calls) == 3
    second = fake({})
    again = router_eval.run_router_eval(second, cases=TWO_CASES)
    assert second.calls == [] and again[0].got == ("nutrition",)                 # served from the cache
    router_eval.run_router_eval(second, cases=TWO_CASES, use_cache=False)
    assert len(second.calls) == 3                                                # --fresh calls again


def test_the_cache_is_keyed_by_the_prompt_so_a_prompt_change_calls_again(monkeypatch):
    router_eval.run_router_eval(fake({}), cases=TWO_CASES)
    monkeypatch.setattr(router_eval, "router_prompt", lambda menu: "a different prompt")
    again = fake({})
    router_eval.run_router_eval(again, cases=TWO_CASES)
    assert len(again.calls) == 3


def test_the_call_budget_stops_a_run():
    with pytest.raises(RuntimeError, match="budget"):
        router_eval.run_router_eval(fake({}), cases=TWO_CASES, max_calls=2)


# ---------- the gate ----------

def test_the_gate_compares_with_the_thresholds():
    t = json.loads(run_llm.THRESHOLDS.read_text(encoding="utf-8"))["router"]
    ok = {"exact_accuracy": 0.97, "nutrition_recall": 1.0, "off_topic_specificity": 0.94, "invalid_json_rate": 0.0, "off_menu_rate": 0.0, "duplicate_rate": 0.0}
    assert run_llm.gate(ok, t) == []
    worse = {**ok, "exact_accuracy": 0.8, "off_menu_rate": 0.2}
    failures = run_llm.gate(worse, t)
    assert len(failures) == 2 and "exact_accuracy" in failures[0] and "off_menu_rate" in failures[1]


def test_the_thresholds_sit_below_the_first_measurement_and_in_the_right_direction():
    t = json.loads(run_llm.THRESHOLDS.read_text(encoding="utf-8"))["router"]
    assert t["exact_accuracy"] <= 0.969 and t["nutrition_recall"] <= 1.0 and t["off_topic_specificity"] <= 0.941
    assert all(t[k] <= 0.1 for k in run_llm.LOWER_IS_BETTER if k in t) and set(t) <= set(run_llm.HIGHER_IS_BETTER + run_llm.LOWER_IS_BETTER)


# ---------- follow-up cases (Step 7.11c, D-098) ----------

def test_the_followup_cases_are_well_formed():
    from evals.router_followups import FOLLOWUPS
    names = set(default_menu())
    assert len(FOLLOWUPS) >= 10 and len({(str(h), m) for _, h, m, _, _, _ in FOLLOWUPS}) == len(FOLLOWUPS)
    for summary, history, message, expected, tags, mentions in FOLLOWUPS:
        assert set(expected) <= names and message.strip() and all(role in ("user", "assistant") for role, _ in history)
        assert (history or summary) and (mentions or not expected or "borderline" in tags)       # a follow-up has context; an answer names its subject
    assert any("SYSTEM" in text for _, h, *_ in FOLLOWUPS for _, text in h)                      # one case plants an instruction in the history


def test_the_followup_eval_sends_the_history_scores_the_task_and_uses_the_cache(tmp_path, monkeypatch):
    from evals.router_followups import FOLLOWUPS
    monkeypatch.setattr(router_eval, "CACHE", tmp_path / "router.json")
    sent = []

    def good(tier, messages, **kw):
        sent.append(messages)
        task = "protein in paneer" if "paneer" in messages[1][1] else "calories in roti"
        return LLMResult(text=json.dumps({"assignments": [{"specialist": "nutrition", "task": task}]}), model="m", input_tokens=10,
                         output_tokens=5, cached_tokens=0, cost_usd=0.001, latency_ms=5)

    case = [FOLLOWUPS[0]]                                                                          # "and how much fat?" after paneer
    r = router_eval.run_followup_eval(good, cases=case)[0]
    assert r.route_ok and r.resolved and "NEW message: and how much fat?" in sent[0][1][1] and "paneer" in sent[0][1][1]
    router_eval.run_followup_eval(good, cases=case)
    assert len(sent) == 1                                                                          # the second run came from the cache
    vague = lambda *a, **k: LLMResult(text='{"assignments": [{"specialist": "nutrition", "task": "and how much fat?"}]}', model="m",
                                      input_tokens=1, output_tokens=1, cached_tokens=0, cost_usd=0.0, latency_ms=1)
    s = router_eval.summarize_followups(router_eval.run_followup_eval(vague, cases=case, use_cache=False))
    assert s["followup_route_accuracy"] == 1.0 and s["followup_resolved_rate"] == 0.0              # right specialist, task NOT rewritten


def test_a_borderline_followup_accepts_nothing_or_the_specialist_and_is_not_task_checked():
    from evals.router_eval import FollowupResult
    ok = lambda got: FollowupResult("m", ("nutrition",), got, ("borderline",), "", True, 1, 0.0, 1)
    assert ok(()).route_ok and ok(("nutrition",)).route_ok and not ok(("other",)).route_ok
