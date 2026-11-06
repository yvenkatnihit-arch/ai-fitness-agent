"""Day candidates, pick validation, ordering and the code fallback (pure Python)."""

import pytest

from app.calc.day_picks import (
    EXERCISES_PER_DAY, day_candidates, fallback_picks, order_picks, pattern_cap, validate_picks, wanted_count,
)
from app.calc.exercise_filter import ExerciseOption
from app.calc.splits import BY_KEY


def ex(key, pattern, muscles, difficulty="beginner", name=None, status="review"):
    return ExerciseOption(id=0, key=key, name=name or key.replace("_", " ").title(), muscle_groups=tuple(muscles),
                          equipment=(), location="both", difficulty=difficulty, movement_pattern=pattern,
                          form_cues=("x",), contraindications=(), review_status=status)


LIB = [
    ex("bench", "push_horizontal", ["chest", "triceps"]),
    ex("pushup", "push_horizontal", ["chest", "shoulders", "triceps"]),
    ex("fly", "push_horizontal", ["chest"]),
    ex("ohp", "push_vertical", ["shoulders", "triceps"]),
    ex("lateral", "push_vertical", ["shoulders"]),
    ex("row", "pull_horizontal", ["back", "biceps"]),
    ex("squat", "squat", ["quads", "glutes"]),
    ex("plank", "core", ["abs"], name="Plank"),
    ex("blocked_one", "push_horizontal", ["chest"], status="blocked"),
    ex("wrong_muscle", "push_horizontal", ["calves"]),      # right pattern, but not a push-day muscle
    ex("cardio_run", "cardio", ["quads"]),
]

def push_day():
    return next(d for s in BY_KEY.values() for d in s.days if d.label == "Push")


def test_candidates_need_a_day_pattern_and_a_day_muscle_and_are_never_blocked():
    keys = [o.key for o in day_candidates(push_day(), LIB)]
    assert set(keys) == {"bench", "pushup", "fly", "ohp", "lateral"}
    assert "blocked_one" not in keys and "wrong_muscle" not in keys and "cardio_run" not in keys and "row" not in keys


def test_candidate_order_is_stable():
    assert day_candidates(push_day(), LIB) == day_candidates(push_day(), list(reversed(LIB)))


def test_wanted_count_by_level_and_never_more_than_the_library_has():
    c = day_candidates(push_day(), LIB)
    assert [wanted_count(level, c) for level in EXERCISES_PER_DAY] == [4, 5, 5]   # only five candidates exist
    assert wanted_count("advanced", c[:2]) == 2


@pytest.mark.parametrize("wanted,patterns,cap", [(5, 1, 5), (4, 2, 3), (6, 6, 3), (6, 1, 6), (5, 0, 5)])
def test_pattern_cap(wanted, patterns, cap):
    assert pattern_cap(wanted, patterns) == cap


def test_a_good_pick_has_no_problems():
    c = day_candidates(push_day(), LIB)
    assert validate_picks(["bench", "ohp", "pushup", "lateral"], c, 4) == []


@pytest.mark.parametrize("keys,fragment", [
    (["bench", "ohp", "pushup", "squat"], "not in the allowed list: squat"),     # real exercise, wrong day
    (["bench", "ohp", "pushup", "made_up_lift"], "not in the allowed list: made_up_lift"),
    (["bench", "bench", "ohp", "lateral"], "repeated: bench"),
    (["bench", "ohp", "pushup"], "need exactly 4 exercises, got 3"),
    (["bench", "ohp", "pushup", "lateral", "fly"], "need exactly 4 exercises, got 5"),
    ("bench", "must be a list"),
    ([1, 2, 3, 4], "must be a list"),
    (None, "must be a list"),
])
def test_bad_picks_are_named(keys, fragment):
    problems = validate_picks(keys, day_candidates(push_day(), LIB), 4)
    assert any(fragment in p for p in problems), problems


def test_too_much_of_one_movement_and_too_little_variety_are_rejected():
    c = day_candidates(push_day(), LIB)
    assert validate_picks(["bench", "pushup", "fly", "ohp"], c, 4) == []   # three of one movement is allowed
    four_same = [ex(f"p{i}", "push_horizontal", ["chest"]) for i in range(4)] + [ex("v", "push_vertical", ["shoulders"])]
    problems = validate_picks(["p0", "p1", "p2", "p3"], four_same, 4)
    assert any("too many from one movement" in p for p in problems)
    assert any("cover at least 2 different movements" in p for p in problems)


def test_order_puts_compound_lifts_before_isolation_before_core():
    c = day_candidates(push_day(), LIB) + [LIB[7]]            # LIB[7] is the plank (a timed core exercise)
    ordered = order_picks(["plank", "lateral", "bench", "fly"], c)
    assert ordered[0] == "bench" and ordered[-1] == "plank" and set(ordered[1:3]) == {"lateral", "fly"}


def test_fallback_is_valid_ordered_deterministic_and_prefers_unused_exercises():
    c = day_candidates(push_day(), LIB)
    a = fallback_picks(c, 4)
    assert validate_picks(a, c, 4) == []
    assert a == fallback_picks(c, 4)
    assert a[0] in {"bench", "pushup", "ohp"}                                  # a compound lift leads
    b = fallback_picks(c, 4, used=a)
    assert validate_picks(b, c, 4) == [] and set(b) != set(a)                   # variety across days when possible


def test_fallback_of_a_one_pattern_day_stays_valid():
    chest = next(d for s in BY_KEY.values() for d in s.days if d.label == "Chest")
    lib = [ex(f"c{i}", "push_horizontal", ["chest"]) for i in range(6)]
    c = day_candidates(chest, lib)
    picks = fallback_picks(c, 5)
    assert len(picks) == 5 and validate_picks(picks, c, 5) == []


def test_fallback_with_too_few_candidates_returns_what_exists():
    assert fallback_picks([LIB[0]], 4) == ["bench"]
