"""Step 7.7d: the workout plan eval HARNESS with a fake model and a made-up exercise library (free). Real run: `python -m evals.run_llm workout`."""

import json
import re

import pytest

from app.calc.exercise_filter import ExerciseOption
from evals import cache as cache_mod
from evals import workout_eval
from evals.workout_cases import SCENARIOS, Scenario, S
from app.llm.client import LLMResult


@pytest.fixture(autouse=True)
def private_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "DIR", tmp_path / "cache")


PATTERN_MUSCLES = {"push_horizontal": ("chest", "triceps"), "push_vertical": ("shoulders", "triceps"), "pull_horizontal": ("back", "biceps"),
                   "pull_vertical": ("back", "biceps"), "squat": ("quads", "glutes"), "hinge": ("hamstrings", "glutes"),
                   "lunge": ("quads", "glutes"), "core": ("abs",)}


def option(key, pattern, muscles, *, difficulty="beginner", location="both", equipment=(), contra=(), status="ready", i=[0]):
    i[0] += 1
    return ExerciseOption(i[0], key, key.replace("_", " ").title(), muscles, equipment, location, difficulty, pattern, ("Keep your back flat",), contra, status)


def library() -> list[ExerciseOption]:
    out = []
    for pattern, muscles in PATTERN_MUSCLES.items():
        for n in range(6):
            out.append(option(f"{pattern}_{n}", pattern, (muscles[n % len(muscles)],) + tuple(m for m in muscles if m != muscles[n % len(muscles)])))
    return out


PPL = S("ppl3 beginner gym", "ppl_3", "beginner", "general_fitness", "gym")


def no_model(cache, counter):
    """A model that answers nothing usable: every day falls back to code."""
    def ask(prompt):
        counter["asks"] += 1
        return LLMResult('{"days": []}', "fake", 10, 5, 0, 0.001, 3)
    return ask


def sensible_model(cache, counter):
    """A fake model that reads the prompt and picks round-robin across movements, within the stated rules."""
    def ask(prompt):
        counter["asks"] += 1
        days = []
        for block in re.split(r"(?m)^(?=Day \d+:)", prompt)[1:]:
            number = int(re.match(r"Day (\d+):", block).group(1))
            wanted = int(re.search(r"exactly (\d+) exercises", block).group(1))
            rows = [line[2:].split(" | ") for line in block.splitlines() if line.startswith("- ")]
            by_pattern: dict[str, list[str]] = {}
            for key, _, _, pattern in rows:
                by_pattern.setdefault(pattern, []).append(key)
            picked = []
            while len(picked) < wanted:
                for keys in by_pattern.values():
                    if keys and len(picked) < wanted:
                        picked.append(keys.pop(0))
            days.append({"day": number, "exercises": picked})
        return LLMResult(json.dumps({"days": days}), "fake", 200, 60, 0, 0.002, 5)
    return ask


# ---------- the independent safety check ----------

def test_a_clean_plan_has_no_safety_violations():
    lib = {o.key: o for o in library()}
    assert workout_eval.safety_violations(list(lib)[:5], lib, PPL) == []


@pytest.mark.parametrize("kwargs, scenario, expect", [
    ({"contra": ("knee",)}, S("a", "ppl_3", "beginner", "fat_loss", "gym", ("knee",)), "hits injury"),
    ({"difficulty": "advanced"}, S("b", "ppl_3", "beginner", "fat_loss", "gym"), "is above beginner"),
    ({"location": "gym"}, S("c", "ppl_3", "beginner", "fat_loss", "home"), "a gym exercise in a home plan"),
    ({"equipment": ("barbell",)}, S("d", "ppl_3", "beginner", "fat_loss", "home", equipment=("dumbbells",)), "needs ['barbell']"),
    ({"status": "blocked"}, S("e", "ppl_3", "beginner", "fat_loss", "gym"), "blocked"),
])
def test_each_kind_of_safety_violation_is_found(kwargs, scenario, expect):
    o = option("x", "squat", ("quads",), **kwargs)
    found = workout_eval.safety_violations(["x"], {"x": o}, scenario)
    assert len(found) == 1 and expect in found[0]


def test_a_gym_plan_ignores_equipment_but_a_home_plan_does_not():
    o = option("x", "squat", ("quads",), equipment=("barbell",))
    assert workout_eval.safety_violations(["x"], {"x": o}, S("g", "ppl_3", "beginner", "fat_loss", "gym")) == []
    assert workout_eval.safety_violations(["x"], {"x": o}, S("h", "ppl_3", "beginner", "fat_loss", "home", equipment=("barbell",))) == []


# ---------- running scenarios ----------

def test_when_the_model_is_useless_every_day_falls_back_and_the_plan_is_still_safe():
    r = workout_eval.run_workout_eval(library(), scenarios=[PPL], call_ask=no_model)[0]
    assert r.sources == ("fallback",) * 3 and r.passed and not r.refused and r.safety == () and r.problems == ()
    assert workout_eval.summarize([r])["model_day_rate"] == 0.0


def test_a_sensible_model_is_credited_for_its_days():
    r = workout_eval.run_workout_eval(library(), scenarios=[PPL], call_ask=sensible_model)[0]
    assert r.sources == ("model",) * 3 and r.passed and r.asks == 1
    s = workout_eval.summarize([r])
    assert s["model_day_rate"] == 1.0 and s["retry_rate"] == 0.0 and s["scenario_pass_rate"] == 1.0 and s["safety_violation_rate"] == 0.0


def test_too_few_safe_exercises_is_a_refusal_not_a_failure():
    tiny = [o for o in library() if o.movement_pattern in ("squat", "hinge", "lunge", "core")]          # no push or pull exercises at all
    r = workout_eval.run_workout_eval(tiny, scenarios=[PPL], call_ask=no_model)[0]
    assert r.refused and "not enough safe exercises for: Push, Pull" in r.refusal      # the Legs day could still be made, so it was asked about
    s = workout_eval.summarize([r])
    assert s["refused"] == 1 and s["refused_rate"] == 1.0 and s["scenario_pass_rate"] == 1.0     # nothing was made, so nothing failed


def test_a_hidden_exercise_is_never_in_the_plan_even_when_the_filter_is_not_the_one_checking():
    lib = library() + [option("hurts_knee", "squat", ("quads",), contra=("knee",))]
    sc = S("knee", "ppl_3", "beginner", "fat_loss", "gym", ("knee",))
    r = workout_eval.run_workout_eval(lib, scenarios=[sc], call_ask=sensible_model)[0]
    assert r.safety == () and r.passed


def test_a_focus_scenario_reports_whether_the_focus_was_honoured():
    sc = S("focus", "ppl_3", "beginner", "fat_loss", "gym", focus=("chest",))
    r = workout_eval.run_workout_eval(library(), scenarios=[sc], call_ask=sensible_model)[0]
    assert r.focus_ok in (0.0, 1.0)
    plain = workout_eval.run_workout_eval(library(), scenarios=[PPL], call_ask=sensible_model)[0]
    assert plain.focus_ok is None


# ---------- the real model path: cache, budget, same settings as the app ----------

def llm_result(prompt_text):
    return LLMResult(prompt_text, "fake", 100, 20, 0, 0.001, 4)


def test_the_eval_uses_the_pickers_own_call_settings(monkeypatch):
    seen = []

    def fake_call(tier, messages, **kw):
        seen.append((tier, kw))
        return llm_result('{"days": []}')
    monkeypatch.setattr(workout_eval, "call_llm", fake_call)
    workout_eval.run_workout_eval(library(), scenarios=[PPL])
    from app.workflows.pick_exercises import PICKER_CALL
    assert seen and all(t == "mid" and kw["thinking_budget"] == 0 and kw["flow"] == "eval" and kw["node"] == PICKER_CALL["node"] for t, kw in seen)
    assert all(kw["max_tokens"] == PICKER_CALL["max_tokens"] and kw["temperature"] == 0.0 and kw["json_mode"] is True for _, kw in seen)


def test_the_cache_serves_a_second_run_and_a_settings_change_calls_again(monkeypatch):
    calls = []
    monkeypatch.setattr(workout_eval, "call_llm", lambda tier, messages, **kw: calls.append(1) or llm_result('{"days": []}'))
    workout_eval.run_workout_eval(library(), scenarios=[PPL])
    first = len(calls)
    workout_eval.run_workout_eval(library(), scenarios=[PPL])
    assert len(calls) == first                                                  # from the cache
    monkeypatch.setattr(workout_eval, "PICKER_CALL", {**workout_eval.PICKER_CALL, "thinking_budget": 512})
    workout_eval.run_workout_eval(library(), scenarios=[PPL])
    assert len(calls) > first                                                   # the settings are part of the cache key


def test_the_call_budget_stops_a_run(monkeypatch):
    monkeypatch.setattr(workout_eval, "call_llm", lambda tier, messages, **kw: llm_result('{"days": []}'))
    with pytest.raises(RuntimeError, match="budget"):
        workout_eval.run_workout_eval(library(), scenarios=[PPL], max_calls=1)


# ---------- summaries and scenarios ----------

def result(**over):
    base = dict(name="x", refused=False, refusal="", safety=(), problems=(), cap_breaches=(), sources=("model", "model"), asks=1, pattern_coverage=1.0,
                counts_ok=1.0, focus_ok=None, repeat_rate=0.0, tokens=100, cost_usd=0.01, latency_ms=1000)
    return workout_eval.WorkoutResult(**{**base, **over})


def test_a_weekly_cap_breach_a_safety_violation_or_a_payload_problem_fails_the_plan():
    assert result().passed
    assert not result(cap_breaches=("back: 56 sets",)).passed
    assert not result(safety=("Squat: hits injury ['knee']",)).passed
    assert not result(problems=("day 1: an exercise appears twice",)).passed


def test_the_summary_separates_safety_from_quality():
    s = workout_eval.summarize([result(), result(sources=("fallback", "model"), asks=2, cap_breaches=("back: 25 sets",)), result(refused=True, sources=("none",))])
    assert s["scenarios"] == 3 and s["refused"] == 1 and s["scenario_pass_rate"] == 0.5 and s["weekly_cap_breach_rate"] == 0.5
    assert s["safety_violation_rate"] == 0.0 and s["retry_rate"] == 0.5 and s["model_day_rate"] == 0.75   # the refused scenario is left out: 3 of the other 4 days were chosen by the model


def test_the_scenario_set_covers_the_hard_cases():
    assert len(SCENARIOS) >= 12 and len({s.name for s in SCENARIOS}) == len(SCENARIOS)
    assert any(len(s.injuries) >= 2 for s in SCENARIOS) and any(s.place == "home" and not s.equipment for s in SCENARIOS)
    assert any(s.focus for s in SCENARIOS) and {s.split_key for s in SCENARIOS} >= {"ppl_3", "upper_lower_4", "bro_5", "ppl_6", "arnold_6"}
    assert all(isinstance(s, Scenario) for s in SCENARIOS)
