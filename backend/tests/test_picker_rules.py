"""Step 7.7d (D-085): the picker states the validator's limits, thinking is off for the picker, and the per-call thinking option works."""

import pytest

from app.calc.day_picks import pattern_cap, validate_picks
from app.calc.exercise_filter import ExerciseOption
from app.llm import client
from app.llm.picker_prompt import DayRequest, build_user_prompt
from app.workflows import pick_exercises as picker


def opt(i, pattern):
    return ExerciseOption(i, f"k{i}", f"Ex {i}", ("chest",), (), "both", "beginner", pattern, ("cue",), (), "ready")


CANDS = [opt(i, "push_horizontal" if i < 6 else "push_vertical") for i in range(10)]


# ---------- the prompt states the rules ----------

def test_the_day_request_states_the_variety_limits():
    prompt = build_user_prompt("beginner", "fat_loss", [DayRequest(1, "Push", 6, CANDS, (), 3, 2)])
    assert "at most 3 exercises with the same movement" in prompt and "at least 2 different movements" in prompt


def test_without_limits_the_prompt_is_unchanged():
    assert "Rules for this day" not in build_user_prompt("beginner", "fat_loss", [DayRequest(1, "Push", 6, CANDS)])


def test_the_limits_come_from_the_same_functions_the_validator_uses():
    cap, variety = picker._day_limits(CANDS, 6)
    assert cap == pattern_cap(6, 2) and variety == 2
    ok = [c.key for c in CANDS[:3]] + [c.key for c in CANDS[6:9]]          # 3 of one movement, 3 of the other: inside the stated limits
    too_many = [c.key for c in CANDS[:6]]                                  # 6 of one movement: outside
    assert validate_picks(ok, CANDS, 6) == []
    assert any("too many from one movement" in p for p in validate_picks(too_many, CANDS, 6))


def test_the_pick_requests_carry_the_limits(monkeypatch):
    seen = []

    def ask(prompt):
        seen.append(prompt)
        raise RuntimeError("stop")          # the picker falls back; we only want the prompt
    from app.calc.splits import split_by_key
    picker.pick_exercises(split_by_key("ppl_3"), [opt(i, p) for i, p in enumerate(["push_horizontal", "push_vertical"] * 8)], "beginner", "fat_loss", ask=ask)
    assert seen and "Rules for this day: at most" in seen[0] and "Count before you answer" in seen[0]


# ---------- thinking ----------

def test_the_picker_turns_hidden_thinking_off():
    assert picker.PICKER_CALL["thinking_budget"] == 0 and picker.PICKER_CALL["max_tokens"] == picker.MAX_TOKENS
    assert picker.PICKER_CALL["temperature"] == 0.0 and picker.PICKER_CALL["json_mode"] is True


def test_the_default_ask_sends_the_pickers_call_settings(monkeypatch):
    seen = {}
    monkeypatch.setattr(picker, "call_llm", lambda tier, messages, **kw: seen.update(tier=tier, **kw) or "result")
    assert picker._default_ask(None)("prompt") == "result"
    assert seen["tier"] == "mid" and seen["thinking_budget"] == 0 and seen["flow"] == "plan_generation" and seen["node"] == "exercise_picker"


@pytest.mark.parametrize("tier, budget, expected", [("small", None, 0), ("small", 512, 512), ("mid", None, None), ("mid", 0, 0), ("mid", 1024, 1024)])
def test_the_thinking_budget_defaults_and_per_call_override(tier, budget, expected):
    assert client.build_chat_model(tier, 100, thinking_budget=budget).thinking_budget == expected
