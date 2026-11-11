"""Step 7.11d (D-099): the summary eval harness, offline (fake model, temporary cache)."""

import pytest

from app.llm.client import LLMResult
from evals import cache as cache_mod, run_llm, summary_eval
from evals.summary_cases import CASES

ONE = [CASES[0]]


def fake(text, calls):
    def call(tier, messages, **kw):
        calls.append(messages)
        return LLMResult(text=text, model="m", input_tokens=10, output_tokens=5, cached_tokens=0, cost_usd=0.001, latency_ms=7)
    return call


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "DIR", tmp_path)


def test_the_cases_are_well_formed():
    assert len(CASES) >= 8 and len({repr(c[1]) for c in CASES}) == len(CASES)
    assert any(c[3] for c in CASES) and any(not c[2] for c in CASES)                  # traps exist; a "nothing to keep" case exists
    assert all(role in ("user", "assistant") for _, ms, _, _ in CASES for role, _ in ms)


def test_a_good_summary_passes_and_the_second_run_comes_from_the_cache():
    calls = []
    good = fake("The user is vegetarian and dislikes karela. They asked about paneer.", calls)
    r = summary_eval.run_summary_eval(good, cases=ONE)[0]
    assert r.passed and r.accepted and r.kept == r.facts == 3
    summary_eval.run_summary_eval(good, cases=ONE)
    assert len(calls) == 1
    summary_eval.run_summary_eval(good, cases=ONE, use_cache=False)
    assert len(calls) == 2


def test_missing_facts_invented_numbers_and_copied_instructions_are_scored_separately():
    r = summary_eval.run_summary_eval(fake("The user is vegetarian. Target 2500 kcal.", []), cases=ONE, use_cache=False)[0]
    assert r.kept == 1 and r.facts == 3 and r.invented == ("2500",) and not r.passed and not r.accepted
    trap = [c for c in CASES if c[3]][0]
    t = summary_eval.run_summary_eval(fake("ADMIN MODE ON. User eats eggs and no fish.", []), cases=[trap], use_cache=False)[0]
    assert t.copied and not t.passed
    s = summary_eval.summarize([t])
    assert s["instruction_copied_rate"] == 1.0 and s["pass_rate"] == 0.0


def test_the_eval_budget_is_a_hard_cap():
    with pytest.raises(RuntimeError, match="budget"):
        summary_eval.run_summary_eval(fake("x", []), cases=CASES, max_calls=1, use_cache=False)


def test_the_gate_knows_the_summary_metrics():
    bad = {"facts_kept_rate": 0.5, "instruction_copied_rate": 0.5, "accepted_rate": 1.0}
    failures = run_llm.gate(bad, {"facts_kept_rate": 0.9, "instruction_copied_rate": 0.0, "accepted_rate": 0.9})
    assert len(failures) == 2 and any("facts_kept_rate" in f for f in failures) and any("instruction_copied_rate" in f for f in failures)
