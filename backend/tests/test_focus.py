"""Focus areas: the extra exercise, the extra sets and the weekly cap (pure Python)."""

import pytest

from app.calc.day_picks import day_candidates, fallback_picks
from app.calc.focus import add_focus_sets, check_focus, day_wanted
from app.calc.splits import BY_KEY
from app.calc.workout_plan import DayPick, build_payload
from app.safety.safety_config import MAX_WEEKLY_SETS_PER_MUSCLE
from tests.test_day_picks import ex
from tests.test_workout_plan import LIB, MONDAY, PICKS, PPL


def day(label):
    return next(d for s in BY_KEY.values() for d in s.days if d.label == label)


def test_focus_list_is_cleaned_and_checked():
    assert check_focus(["chest", "chest", "glutes"]) == ["chest", "glutes"]
    assert check_focus([]) == []
    for bad in (["biceps", "chest", "back"], ["forearms"], ["Chest"], ["full_body"]):
        with pytest.raises(ValueError):
            check_focus(bad)


def test_a_day_that_trains_a_focus_muscle_gets_one_more_exercise():
    assert day_wanted(5, day("Push"), ["chest"]) == 6
    assert day_wanted(5, day("Pull"), ["chest"]) == 5            # a pull day does not train chest
    assert day_wanted(5, day("Legs"), ["glutes", "chest"]) == 6
    assert day_wanted(8, day("Push"), ["chest"]) == 8            # never above the overall maximum
    assert day_wanted(5, day("Push"), []) == 5


def week(sets_per_exercise, n_days=3):
    """A small fake week: bench + fly (chest) each day."""
    return [{"exercises": [{"exercise_key": "bench", "sets": sets_per_exercise}, {"exercise_key": "curl", "sets": sets_per_exercise}]}
            for _ in range(n_days)]


MUSCLES = {"bench": ["chest", "triceps"], "curl": ["biceps"]}


def test_each_focus_exercise_gets_one_more_set_and_others_do_not():
    days = week(3)
    assert add_focus_sets(days, MUSCLES, ["chest"]) == 3
    assert [[e["sets"] for e in d["exercises"]] for d in days] == [[4, 3]] * 3


def test_an_exercise_already_at_the_set_maximum_gets_nothing():
    days = week(5)
    assert add_focus_sets(days, MUSCLES, ["chest"]) == 0


def test_the_weekly_cap_stops_extra_sets():
    cap = MAX_WEEKLY_SETS_PER_MUSCLE
    days = week(4, n_days=5)                         # chest already 5 x 4 = 20 = the cap
    assert add_focus_sets(days, MUSCLES, ["chest"]) == 0
    days = week(4, n_days=4)                         # chest 16: room for exactly 4 more
    assert add_focus_sets(days, MUSCLES, ["chest"]) == cap - 16
    assert sum(d["exercises"][0]["sets"] for d in days) == cap


def test_a_compound_lift_only_gets_a_set_if_every_focus_muscle_it_trains_has_room():
    days = [{"exercises": [{"exercise_key": "bench", "sets": 4}] * 1} for _ in range(5)]   # chest 20 (full), triceps 20 (full)
    days.append({"exercises": [{"exercise_key": "bench", "sets": 3}]})                     # chest/triceps now 23: over already
    assert add_focus_sets(days, MUSCLES, ["chest", "biceps"]) == 0


def test_no_focus_changes_nothing():
    days = week(3)
    assert add_focus_sets(days, MUSCLES, []) == 0 and days == week(3)


def test_the_plan_payload_gives_focus_muscles_more_sets():
    base = build_payload(PPL, PICKS, LIB, level="intermediate", goal="muscle_gain", pace="normal", flagged=False, week_start=MONDAY)
    boosted = build_payload(PPL, PICKS, LIB, level="intermediate", goal="muscle_gain", pace="normal", flagged=False,
                            week_start=MONDAY, focus=["chest"])
    sets = lambda p: {e["exercise_key"]: e["sets"] for d in p["days"] for e in d["exercises"]}
    assert sets(boosted)["bench"] == sets(base)["bench"] + 1          # bench trains chest
    assert sets(boosted)["row"] == sets(base)["row"]                  # a row does not
    assert boosted["focus_areas"] == ["chest"] and boosted["focus_sets_added"] >= 1
    assert base["focus_areas"] == [] and base["focus_sets_added"] == 0
    push_base, push_boost = base["days"][0], boosted["days"][0]
    assert push_boost["minutes"] >= push_base["minutes"]               # the day got longer, and says so


def test_users_with_a_health_flag_get_no_extra_volume():
    flagged = build_payload(PPL, PICKS, LIB, level="intermediate", goal="muscle_gain", pace="normal", flagged=True,
                            week_start=MONDAY, focus=["chest"])
    plain = build_payload(PPL, PICKS, LIB, level="intermediate", goal="muscle_gain", pace="normal", flagged=True, week_start=MONDAY)
    assert flagged["days"] == plain["days"] and flagged["focus_areas"] == [] and flagged["focus_sets_added"] == 0


def test_the_code_fallback_prefers_focus_exercises():
    push = day("Push")
    allowed = [ex("flat", "push_horizontal", ["chest"], name="Flat press"),
               ex("ohp_a", "push_horizontal", ["shoulders"], name="A first alphabetically"),
               ex("lat", "push_vertical", ["shoulders"], name="Lateral raise")]
    cands = day_candidates(push, allowed)
    assert fallback_picks(cands, 2)[0] == "ohp_a"                          # without focus: the alphabetical one wins
    assert fallback_picks(cands, 2, focus=["chest"])[0] == "flat"          # with a chest focus: the chest exercise leads
