"""Step 7.7a: the regression gate. Running the guard evals inside pytest means a change that weakens a guard fails the build."""

from evals import guards
from evals.guard_cases import CASES


def results():
    return guards.run_cases()


def test_every_critical_case_passes():
    critical, _, _ = guards.gate(results(), guards.load_baseline())
    assert critical == [], [(r.text, r.expected, r.got) for r in critical]


def test_nothing_that_passed_in_the_baseline_fails_now():
    _, regressions, _ = guards.gate(results(), guards.load_baseline())
    assert regressions == [], [(r.text, r.expected, r.got) for r in regressions]


def test_the_baseline_is_up_to_date_with_the_cases():
    ids = {f"{kind}:{text}" for kind, text, _, _ in CASES}
    baseline = guards.load_baseline()
    assert baseline <= ids, "the baseline lists cases that no longer exist: run python -m evals.run --update-baseline"
    _, _, improvements = guards.gate(results(), baseline)
    assert improvements == [], "cases improved or were added: run python -m evals.run --update-baseline to lock them in"


def test_case_ids_are_unique():
    ids = [f"{kind}:{text}" for kind, text, _, _ in CASES]
    assert len(ids) == len(set(ids))


def test_the_dataset_covers_every_category_with_harmless_messages_and_known_gaps():
    expected = {e for _, _, e, _ in CASES if e}
    assert expected == {"crisis", "eating_disorder", "extreme_diet", "medical", "red_flag_pain", "injection", "unsafe_output"}
    assert sum(1 for _, _, e, t in CASES if e is None and "gap" not in t) >= 15
    assert sum(1 for *_, t in CASES if "critical" in t) >= 8 and sum(1 for *_, t in CASES if "gap" in t) >= 20


# ---------- the gate itself must catch a regression (tested with made-up results) ----------

def made(case_id, expected, got, tags=()):
    return guards.Result(case_id, "in", case_id, expected, got, tags)


def test_the_gate_flags_a_case_that_used_to_pass_and_now_fails():
    r = [made("a", "crisis", None), made("b", None, None)]
    critical, regressions, improvements = guards.gate(r, baseline={"a", "b"})
    assert [x.id for x in regressions] == ["a"] and critical == [] and improvements == []


def test_the_gate_flags_a_critical_failure_even_if_the_baseline_does_not_know_it():
    critical, regressions, _ = guards.gate([made("c", "crisis", None, ("critical",))], baseline=set())
    assert [x.id for x in critical] == ["c"] and regressions == []


def test_the_gate_reports_an_improvement_without_failing():
    critical, regressions, improvements = guards.gate([made("g", "crisis", "crisis", ("gap",))], baseline=set())
    assert critical == [] and regressions == [] and [x.id for x in improvements] == ["g"]


def test_the_summary_counts_recall_false_positives_and_gaps():
    s = guards.summarize([made("a", "crisis", "crisis"), made("b", "crisis", None), made("c", None, "medical"), made("d", None, None),
                          made("e", "crisis", None, ("gap",)), made("f", "crisis", "crisis", ("gap",))])
    assert s["recall_by_category"] == {"crisis": 0.5} and s["false_positive_rate"] == 0.5
    assert s["known_gaps"] == 2 and s["known_gaps_now_passing"] == 1 and s["gap_recall"] == 0.5
