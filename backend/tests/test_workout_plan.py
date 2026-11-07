"""Building and validating the workout payload (pure Python)."""

import copy
from datetime import date

import pytest

from app.calc.routine import prescribe
from app.calc.splits import BY_KEY, CATALOGUE
from app.calc.workout_plan import WEEK_LAYOUT, DayPick, build_payload, next_monday, summarize, validate_payload
from tests.test_day_picks import ex

LIB = {o.key: o for o in [
    ex("bench", "push_horizontal", ["chest", "triceps"]), ex("ohp", "push_vertical", ["shoulders", "triceps"]),
    ex("lateral", "push_vertical", ["shoulders"]), ex("row", "pull_horizontal", ["back", "biceps"]),
    ex("pulldown", "pull_vertical", ["back", "biceps"]), ex("curl", "pull_vertical", ["biceps"]),
    ex("squat", "squat", ["quads", "glutes"]), ex("rdl", "hinge", ["hamstrings", "glutes"]),
    ex("calf", "squat", ["calves"]), ex("plank", "core", ["abs"], name="Plank"),
    ex("treadmill", "cardio", ["quads"], name="Treadmill"),
]}
PPL = BY_KEY["ppl_3"]
PICKS = [DayPick("Push", ["bench", "ohp", "lateral"]), DayPick("Pull", ["row", "pulldown", "curl"]),
         DayPick("Legs", ["squat", "rdl", "calf", "plank"])]
MONDAY = date(2026, 11, 9)


def build(picks=PICKS, split=PPL, **kw):
    args = dict(level="intermediate", goal="muscle_gain", pace="normal", flagged=False, week_start=MONDAY)
    return build_payload(split, picks, LIB, **{**args, **kw})


@pytest.mark.parametrize("today,monday", [
    (date(2026, 11, 9), date(2026, 11, 9)),    # Monday: starts today
    (date(2026, 11, 10), date(2026, 11, 16)),  # Tuesday
    (date(2026, 11, 15), date(2026, 11, 16)),  # Sunday
    (date(2026, 11, 6), date(2026, 11, 9)),    # Friday
])
def test_next_monday(today, monday):
    assert next_monday(today) == monday and monday.weekday() == 0


def test_every_split_in_the_catalogue_has_a_weekday_layout():
    for split in CATALOGUE:
        days = WEEK_LAYOUT[split.training_days]
        assert len(days) == split.training_days == len(set(days)) and all(1 <= d <= 7 for d in days)


def test_three_day_split_is_monday_wednesday_friday_with_rest_between():
    days = build()["days"]
    assert [d["day_of_week"] for d in days] == [1, 2, 3, 4, 5, 6, 7]
    assert [(d["focus"], d["is_rest"]) for d in days] == [
        ("Push", False), ("Rest", True), ("Pull", False), ("Rest", True), ("Legs", False), ("Rest", True), ("Rest", True)]
    assert all(d["exercises"] == [] for d in days if d["is_rest"])


def test_numbers_come_from_the_routine_rules_not_from_anywhere_else():
    first = build()["days"][0]["exercises"][0]                     # bench: a compound lift
    rx = prescribe("intermediate", "muscle_gain", "normal", "push_horizontal", ["chest", "triceps"], "Bench")
    assert (first["sets"], first["reps_min"], first["reps_max"], first["rest_sec"]) == (rx.sets, rx.reps_min, rx.reps_max, rx.rest_sec)
    assert (first["sets"], first["reps_min"], first["reps_max"], first["rest_sec"]) == (3, 6, 10, 120)   # D-049 by hand
    lateral = build()["days"][0]["exercises"][2]                   # one muscle: isolation
    assert lateral["rest_sec"] == 60


def test_a_timed_exercise_is_a_hold_not_reps():
    plank = build()["days"][4]["exercises"][3]
    assert (plank["reps_min"], plank["reps_max"]) == (1, 1) and plank["note"] == "Hold 30-45 seconds"


def test_health_flags_mean_one_set_fewer_but_never_below_two_and_a_doctor_note():
    normal, flagged = build(), build(flagged=True)
    assert normal["doctor_note"] is None and "check with your doctor" in flagged["doctor_note"]
    for n_day, f_day in zip(normal["days"], flagged["days"]):
        for n, f in zip(n_day["exercises"], f_day["exercises"]):
            assert f["sets"] == max(2, n["sets"] - 1)
    beginner = build(level="beginner", flagged=True)
    assert min(e["sets"] for d in beginner["days"] for e in d["exercises"]) == 2


def test_cardio_is_skipped_and_positions_stay_contiguous():
    payload = build([DayPick("Push", ["bench", "treadmill", "ohp"])] + PICKS[1:])
    assert [(e["exercise_key"], e["position"]) for e in payload["days"][0]["exercises"]] == [("bench", 1), ("ohp", 2)]


def test_the_wrong_number_of_days_is_a_programming_error():
    with pytest.raises(ValueError):
        build(PICKS[:2])


def test_summary_is_one_short_line():
    text = summarize(build())
    assert text == "Push / Pull / Legs, 3 days a week: Mon Push, Wed Pull, Fri Legs. 10 exercises, starting 2026-11-09."
    assert len(text) <= 500


def test_a_good_payload_validates():
    assert validate_payload(build(), set(LIB)) == []


def mutate(change):
    payload = copy.deepcopy(build())
    change(payload)
    return validate_payload(payload, set(LIB))


@pytest.mark.parametrize("change,fragment", [
    (lambda p: p["days"][0]["exercises"][0].update(exercise_key="invented"), "not in the exercise library"),
    (lambda p: p["days"][0]["exercises"][0].update(sets=0), "sets must be 1 to 10"),
    (lambda p: p["days"][0]["exercises"][0].update(sets=11), "sets must be 1 to 10"),
    (lambda p: p["days"][0]["exercises"][0].update(reps_min=12, reps_max=8), "bad reps range"),
    (lambda p: p["days"][0]["exercises"][0].update(rest_sec=601), "rest must be 0 to 600"),
    (lambda p: p["days"][0]["exercises"][1].update(position=5), "wrong position"),
    (lambda p: p["days"][0]["exercises"].append(dict(p["days"][0]["exercises"][0], position=4)), "appears twice"),
    (lambda p: p["days"][0].update(exercises=[]), "needs 1 to 10 exercises"),
    (lambda p: p["days"][1].update(exercises=[p["days"][0]["exercises"][0]]), "rest day has exercises"),
    (lambda p: p["days"].pop(), "exactly seven days"),
    (lambda p: p.update(kind="meal_plan"), "not a workout plan"),
    (lambda p: [d.update(is_rest=True, exercises=[]) for d in p["days"]], "at least one training day"),
])
def test_bad_payloads_are_caught(change, fragment):
    assert any(fragment in problem for problem in mutate(change))


@pytest.mark.parametrize("junk", [None, [], "plan", 5, {"kind": "workout_plan"}, {"kind": "workout_plan", "days": "x"}])
def test_junk_is_not_a_plan(junk):
    assert validate_payload(junk, set(LIB))


def test_each_training_day_says_about_how_long_it_takes_and_rest_days_say_nothing():
    days = build()["days"]
    # Push by hand: bench 3x(40+120)+30 = 510 s, overhead press 510 s, lateral raise 3x(40+60)+30 = 330 s,
    # plus a 300 s warm-up = 1650 s = 27.5 min, which rounds to 30. Legs: 510+510+330+285 (plank) +300 = 32.25 -> 30.
    assert [d["minutes"] for d in days if not d["is_rest"]] == [30, 30, 30]
    assert all(d["minutes"] is None for d in days if d["is_rest"])
