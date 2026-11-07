"""The pick workflow with a fake model: good answers, bad answers, retries, fallbacks, outages."""

import json

import pytest

from app.calc.day_picks import day_candidates, validate_picks
from app.calc.splits import BY_KEY
from app.llm.client import LLMBusy, LLMResult
from app.llm.picker_prompt import SYSTEM, parse_answer
from app.workflows.pick_exercises import pick_exercises
from tests.test_day_picks import LIB, ex  # noqa: I001  (shared little library)

SPLIT = BY_KEY["ppl_3"]
ALLOWED = LIB + [
    ex("curl", "pull_vertical", ["biceps"]), ex("pulldown", "pull_vertical", ["back", "biceps"]),
    ex("face_pull", "pull_horizontal", ["back", "shoulders"]), ex("shrug", "pull_horizontal", ["traps"]),
    ex("deadlift", "hinge", ["hamstrings", "glutes"]), ex("lunge", "lunge", ["quads", "glutes"]),
    ex("calf_raise", "squat", ["calves"]),
]


def reply(days):
    return LLMResult(json.dumps({"days": days}), "m", 10, 10, 0, 0.0, 5)


class Script:
    """Fake `ask`: returns the next scripted reply (or raises it) and remembers the prompts it was given."""

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def run(ask, level="beginner"):
    return pick_exercises(SPLIT, ALLOWED, level, "muscle_gain", ask=ask)


def good_for(level="beginner"):
    """What a perfect model would answer: our own fallback picks, per day."""
    from app.calc.day_picks import fallback_picks, wanted_count
    out = []
    for n, day in enumerate(SPLIT.days, 1):
        c = day_candidates(day, ALLOWED)
        out.append({"day": n, "exercises": fallback_picks(c, wanted_count(level, c))})
    return out


def test_a_good_answer_is_used_as_is_with_one_call():
    ask = Script(reply(good_for()))
    result = run(ask)
    assert [r.source for r in result] == ["model"] * len(SPLIT.days)
    assert len(ask.prompts) == 1
    for day, r in zip(SPLIT.days, result):
        assert validate_picks(list(r.keys), day_candidates(day, ALLOWED), len(r.keys)) == []


def test_the_prompt_lists_only_allowed_exercises_and_no_numbers_are_asked_for():
    ask = Script(reply(good_for()))
    run(ask)
    prompt = ask.prompts[0]
    assert "blocked_one" not in prompt and "cardio_run" not in prompt and "wrong_muscle" not in prompt
    assert "Do not write sets, reps, weights" in SYSTEM


def test_a_made_up_exercise_is_rejected_and_that_day_is_asked_again():
    bad = good_for()
    bad[0] = {"day": 1, "exercises": ["bench", "ohp", "pushup", "super_secret_lift"]}
    ask = Script(reply(bad), reply([good_for()[0]]))
    result = run(ask)
    assert result[0].source == "model" and "super_secret_lift" not in result[0].keys
    assert len(ask.prompts) == 2
    assert "rejected" in ask.prompts[1] and "super_secret_lift" in ask.prompts[1]
    assert "Day 2" not in ask.prompts[1]            # only the failed day is re-asked


def test_two_bad_answers_fall_back_to_code_picks_that_are_valid():
    bad = {"day": 1, "exercises": ["nope", "nope2", "nope3", "nope4"]}
    ask = Script(reply([bad] + good_for()[1:]), reply([bad]))
    result = run(ask)
    assert result[0].source == "fallback" and "not in the allowed list" in result[0].note
    assert validate_picks(list(result[0].keys), day_candidates(SPLIT.days[0], ALLOWED), 4) == []
    assert all(r.source == "model" for r in result[1:])


def test_garbage_text_means_fallback_for_every_day():
    ask = Script(LLMResult("sorry, I cannot do that", "m", 1, 1, 0, 0, 1), LLMResult("{}", "m", 1, 1, 0, 0, 1))
    result = run(ask)
    assert [r.source for r in result] == ["fallback"] * len(SPLIT.days)
    assert all(len(r.keys) == 4 for r in result)


def test_a_missing_day_is_asked_again():
    ask = Script(reply(good_for()[:-1]), reply([good_for()[-1]]))
    result = run(ask)
    assert [r.source for r in result] == ["model"] * len(SPLIT.days)


def test_an_outage_still_gives_a_complete_valid_plan():
    result = run(Script(LLMBusy()))
    assert [r.source for r in result] == ["fallback"] * len(SPLIT.days)
    assert all(r.keys for r in result)


def test_a_day_with_nothing_allowed_is_reported_not_invented():
    only_push = [o for o in ALLOWED if o.movement_pattern.startswith("push")]
    ask = Script(reply([d for d in good_for() if d["day"] == 1]))
    result = pick_exercises(SPLIT, only_push, "beginner", "muscle_gain", ask=ask)
    assert result[0].source == "model"
    empties = [r for r in result[1:] if r.source == "none"]
    assert empties and all(r.keys == () and "at least 3" in r.note for r in empties)


def test_the_week_gets_variety_when_the_model_is_not_used():
    full = BY_KEY["full_body_3"]
    result = pick_exercises(full, ALLOWED, "beginner", "general_fitness", ask=Script(LLMBusy()))
    assert all(r.source == "fallback" for r in result)
    assert len({r.keys for r in result}) > 1 or len(ALLOWED) < 12     # days differ when the library allows it


@pytest.mark.parametrize("text,expected", [
    ('{"days": [{"day": 1, "exercises": ["a", "b"]}]}', {1: ["a", "b"]}),
    ('```json\n{"days": [{"day": 2, "exercises": ["a"]}]}\n```', {2: ["a"]}),
    ("not json", {}), ("[1, 2]", {}), ('{"days": "x"}', {}), ('{"days": [{"day": "1", "exercises": []}]}', {}),
])
def test_parse_answer(text, expected):
    assert parse_answer(text) == expected


def test_a_day_with_only_two_possible_exercises_is_not_a_workout():
    two = [ex("a", "push_horizontal", ["chest"]), ex("b", "push_vertical", ["shoulders"])]
    result = pick_exercises(SPLIT, two, "beginner", "muscle_gain", ask=Script())    # never asks the model: nothing to choose
    assert [r.source for r in result] == ["none"] * 3 and "Only 2 exercise(s)" in result[0].note


def test_focus_muscles_add_one_exercise_to_their_days_and_reach_the_prompt():
    ask = Script(reply(good_for()))                       # day lists of 4 (beginner): the extra one is asked for, then rejected
    result = pick_exercises(SPLIT, ALLOWED, "beginner", "muscle_gain", focus=["biceps"], ask=ask)
    assert "Priority muscles to bring up: biceps" in ask.prompts[0]
    assert "Day 2: Pull. Choose exactly 5 exercises" in ask.prompts[0]      # the pull day trains biceps: 4 + 1
    assert "Day 1: Push. Choose exactly 4 exercises" in ask.prompts[0]      # the push day does not
    assert [len(r.keys) for r in result][0] == 4


def test_without_focus_nothing_extra_is_asked_for():
    ask = Script(reply(good_for()))
    pick_exercises(SPLIT, ALLOWED, "beginner", "muscle_gain", ask=ask)
    assert "Priority muscles" not in ask.prompts[0]
