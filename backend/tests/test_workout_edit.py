"""Hand edits of the workout plan: the pure rules (no database, no LLM)."""

import copy

import pytest

from app.calc.workout_edit import (
    EditRefused, add_exercise, friendly_reason, move_day, options_for, remove_exercise, swap_exercise, weekly_sets,
)
from app.calc.workout_plan import MAX_EXERCISES_PER_DAY
from tests.test_day_picks import ex

LIBRARY = {o.key: o for o in [
    ex("bench", "push_horizontal", ["chest", "triceps"], "intermediate", "Barbell Bench Press"),
    ex("incline", "push_horizontal", ["chest", "shoulders"], "intermediate", "Incline Dumbbell Press"),
    ex("pushup", "push_horizontal", ["chest", "triceps"], "beginner", "Push-Up"),
    ex("ohp", "push_vertical", ["shoulders", "triceps"], "intermediate", "Overhead Press"),
    ex("lateral", "push_vertical", ["shoulders"], "beginner", "Lateral Raise"),
    ex("dips", "push_vertical", ["triceps", "chest"], "advanced", "Weighted Dips"),
    ex("row", "pull_horizontal", ["back", "biceps"], "intermediate", "Barbell Row"),
    ex("pulldown", "pull_vertical", ["back", "biceps"], "beginner", "Lat Pulldown"),
    ex("curl", "pull_vertical", ["biceps"], "beginner", "Curl"),
    ex("squat", "squat", ["quads", "glutes"], "intermediate", "Back Squat"),
    ex("legpress", "squat", ["quads", "glutes"], "beginner", "Leg Press"),
    ex("rdl", "hinge", ["hamstrings", "glutes"], "intermediate", "Romanian Deadlift"),
    ex("plank", "core", ["abs"], "beginner", "Plank"),
    ex("treadmill", "cardio", ["quads"], "beginner", "Treadmill"),
    ex("banned", "push_horizontal", ["chest"], "beginner", "Banned Press", status="blocked"),
]}
KEYS = set(LIBRARY)
KNEE = {"squat", "legpress"}     # pretend these are tagged for a knee injury


def why_not(key):
    if key in KNEE:
        return "injury: knee"
    if key == "dips":
        return "too hard: advanced"
    if key == "pulldown":
        return "needs equipment: cable_machine"
    return None


RULES = dict(library=LIBRARY, why_not=why_not, level="intermediate", goal="muscle_gain", pace="normal", flagged=False, known_keys=KEYS)


def make_plan(spec):
    """spec: {weekday: [(exercise key, sets), ...]}; days not listed are rest days."""
    days = []
    for dow in range(1, 8):
        rows = spec.get(dow)
        days.append({
            "day_of_week": dow, "focus": f"Day {dow}" if rows else "Rest", "is_rest": not rows, "minutes": None if not rows else 30,
            "exercises": [{"exercise_key": k, "name": LIBRARY[k].name, "position": i, "sets": s, "reps_min": 8, "reps_max": 12,
                           "rest_sec": 90, "note": None} for i, (k, s) in enumerate(rows or [], 1)],
        })
    return {"kind": "workout_plan", "version": 1, "week_start": "2026-11-09", "days": days}


PLAN = make_plan({1: [("bench", 3), ("ohp", 3), ("lateral", 3)], 3: [("row", 3), ("curl", 3)], 5: [("rdl", 3), ("plank", 3)]})


def keys(plan, dow):
    return [e["exercise_key"] for e in plan["days"][dow - 1]["exercises"]]


# --- move a day ---

def test_a_day_moves_to_a_rest_day_and_the_old_day_becomes_rest():
    new, message = move_day(PLAN, 1, 2, KEYS)
    assert keys(new, 2) == ["bench", "ohp", "lateral"] and new["days"][1]["focus"] == "Day 1" and not new["days"][1]["is_rest"]
    assert new["days"][0]["is_rest"] and new["days"][0]["exercises"] == [] and new["days"][0]["focus"] == "Rest"
    assert message == "Moved Day 1 from Monday to Tuesday."


def test_moving_onto_another_training_day_swaps_the_two():
    new, message = move_day(PLAN, 1, 3, KEYS)
    assert keys(new, 1) == ["row", "curl"] and keys(new, 3) == ["bench", "ohp", "lateral"]
    assert (new["days"][0]["focus"], new["days"][2]["focus"]) == ("Day 3", "Day 1") and "Swapped" in message


def test_the_original_plan_is_never_changed():
    before = copy.deepcopy(PLAN)
    move_day(PLAN, 1, 2, KEYS)
    swap_exercise(PLAN, 1, 1, "incline", **RULES)
    add_exercise(PLAN, 1, "pushup", **RULES)
    remove_exercise(PLAN, 1, 1, LIBRARY, KEYS)
    assert PLAN == before


def test_day_lengths_are_recomputed_after_a_move():
    new, _ = move_day(PLAN, 1, 2, KEYS)
    assert new["days"][0]["minutes"] is None and new["days"][1]["minutes"] and new["days"][1]["minutes"] > 0


@pytest.mark.parametrize("args,fragment", [
    ((2, 4), "is a rest day"),            # moving a rest day
    ((1, 1), "already the day"),
    ((0, 2), "Monday to Sunday"),
    ((1, 8), "Monday to Sunday"),
    ((1, "x"), "Monday to Sunday"),
])
def test_bad_day_moves_are_refused(args, fragment):
    with pytest.raises(EditRefused) as e:
        move_day(PLAN, *args, KEYS)
    assert fragment in str(e.value)


# --- swap an exercise ---

def test_a_swap_keeps_the_position_and_gets_the_rules_prescription():
    new, message = swap_exercise(PLAN, 1, 1, "incline", **RULES)
    swapped = new["days"][0]["exercises"][0]
    assert (swapped["exercise_key"], swapped["position"], swapped["name"]) == ("incline", 1, "Incline Dumbbell Press")
    assert (swapped["sets"], swapped["reps_min"], swapped["reps_max"], swapped["rest_sec"]) == (3, 6, 10, 120)   # intermediate, muscle gain, compound
    assert keys(new, 1) == ["incline", "ohp", "lateral"] and message == "Swapped Barbell Bench Press for Incline Dumbbell Press on Monday."


def test_a_swap_may_use_another_movement_if_it_trains_a_shared_muscle():
    new, _ = swap_exercise(PLAN, 1, 2, "pushup", **RULES)      # ohp (shoulders, triceps) <- push-up (chest, triceps)
    assert keys(new, 1)[1] == "pushup"


def test_a_health_flag_takes_a_set_off_the_new_exercise():
    new, _ = swap_exercise(PLAN, 1, 1, "incline", **{**RULES, "flagged": True})
    assert new["days"][0]["exercises"][0]["sets"] == 2


@pytest.mark.parametrize("key,fragment", [
    ("squat", "could aggravate your knee"),                      # an injury
    ("pulldown", "you do not have the equipment (cable machine)"),
    ("dips", "harder than your experience level"),
    ("banned", "not in our library"),                           # blocked
    ("made_up", "not in our library"),
    ("ohp", "already on Monday"),
    ("curl", "same muscles as Barbell Bench Press"),             # unrelated to the exercise being replaced
    ("treadmill", "same muscles"),
])
def test_unsuitable_swaps_are_refused_with_a_reason(key, fragment):
    with pytest.raises(EditRefused) as e:
        swap_exercise(PLAN, 1, 1, key, **RULES)
    assert fragment in str(e.value)


def test_cardio_that_would_otherwise_fit_is_refused():
    with pytest.raises(EditRefused) as e:
        swap_exercise(make_plan({1: [("squat", 3), ("legpress", 3)]}), 1, 1, "treadmill",     # shares the quads, so only "cardio" stops it
                      
                      **{**RULES, "why_not": lambda k: None})
    assert "cardio or mobility" in str(e.value)


@pytest.mark.parametrize("day,position", [(2, 1), (1, 9), (1, 0)])
def test_swapping_something_that_is_not_there_is_refused(day, position):
    with pytest.raises(EditRefused) as e:
        swap_exercise(PLAN, day, position, "incline", **RULES)
    assert "no such exercise" in str(e.value)


# --- remove ---

def test_removing_renumbers_the_rest():
    new, message = remove_exercise(PLAN, 1, 2, LIBRARY, KEYS)
    assert keys(new, 1) == ["bench", "lateral"] and [e["position"] for e in new["days"][0]["exercises"]] == [1, 2]
    assert message == "Removed Overhead Press from Monday."


def test_the_last_exercise_of_a_day_cannot_be_removed():
    with pytest.raises(EditRefused) as e:
        remove_exercise(make_plan({1: [("bench", 3)]}), 1, 1, LIBRARY, KEYS)
    assert "at least one exercise" in str(e.value)


@pytest.mark.parametrize("day,position", [(2, 1), (1, 5)])
def test_removing_something_that_is_not_there_is_refused(day, position):
    with pytest.raises(EditRefused):
        remove_exercise(PLAN, day, position, LIBRARY, KEYS)


# --- add ---

def test_an_added_exercise_goes_at_the_end_with_the_rules_prescription():
    new, message = add_exercise(PLAN, 3, "pulldown", **{**RULES, "why_not": lambda k: None})
    added = new["days"][2]["exercises"][-1]
    assert (added["exercise_key"], added["position"]) == ("pulldown", 3) and added["sets"] == 3 and message == "Added Lat Pulldown to Wednesday."


def test_adding_to_a_rest_day_is_refused():
    with pytest.raises(EditRefused) as e:
        add_exercise(PLAN, 2, "incline", **RULES)
    assert "rest day" in str(e.value)


@pytest.mark.parametrize("key,fragment", [("squat", "knee"), ("bench", "already on Monday"), ("made_up", "not in our library")])
def test_unsuitable_additions_are_refused(key, fragment):
    with pytest.raises(EditRefused) as e:
        add_exercise(PLAN, 1, key, **RULES)
    assert fragment in str(e.value)


def test_a_day_has_at_most_ten_exercises():
    full = make_plan({1: [("bench", 2), ("ohp", 2), ("lateral", 2), ("row", 2), ("curl", 2), ("rdl", 2), ("plank", 2), ("pushup", 2),
                          ("incline", 2), ("legpress", 2)]})
    assert len(full["days"][0]["exercises"]) == MAX_EXERCISES_PER_DAY
    with pytest.raises(EditRefused) as e:
        add_exercise(full, 1, "squat", **{**RULES, "why_not": lambda k: None})
    assert "at most 10" in str(e.value)


# --- the weekly hard-set cap ---

CHEST_HEAVY = make_plan({d: [("bench", 5), ("lateral", 3)] for d in (1, 3, 5, 6)})      # chest: 4 days x 5 sets = 20 (the cap)


def test_weekly_sets_count_an_exercise_for_its_main_muscle_only():
    totals = weekly_sets(PLAN, LIBRARY)
    assert totals == {"chest": 3, "shoulders": 6, "back": 3, "biceps": 3, "hamstrings": 3, "abs": 3}      # by main muscle only


def test_an_edit_cannot_push_a_muscle_past_twenty_sets_a_week():
    with pytest.raises(EditRefused) as e:
        add_exercise(CHEST_HEAVY, 1, "incline", **RULES)                       # + 3 chest sets -> 23
    assert "more than 20 hard sets a week on chest" in str(e.value)
    with pytest.raises(EditRefused):
        swap_exercise(CHEST_HEAVY, 1, 2, "incline", **RULES)                   # lateral raise (no chest) -> incline press: chest up


def test_a_plan_already_at_the_cap_can_still_be_reduced_or_kept_level():
    reduced, _ = swap_exercise(CHEST_HEAVY, 1, 1, "incline", **RULES)           # bench 5 sets -> incline 3 sets: chest 18
    assert weekly_sets(reduced, LIBRARY)["chest"] == 18
    removed, _ = remove_exercise(CHEST_HEAVY, 1, 1, LIBRARY, KEYS)
    assert weekly_sets(removed, LIBRARY)["chest"] == 15


def test_a_plan_over_the_cap_may_not_get_worse_but_other_muscles_are_free():
    over = make_plan({d: [("bench", 6), ("lateral", 3)] for d in (1, 3, 5, 6)})           # chest 24 (already over)
    with pytest.raises(EditRefused):
        add_exercise(over, 1, "pushup", **RULES)
    new, _ = add_exercise(over, 1, "curl", **RULES)                             # biceps are nowhere near the cap
    assert keys(new, 1)[-1] == "curl"


# --- options for the screen ---

def test_swap_options_are_only_exercises_that_fit_and_are_allowed():
    names = [o.key for o in options_for(PLAN, 1, 1, LIBRARY, why_not)]                  # replacing the bench press
    assert names == ["pushup", "incline"]                                              # beginner first, then by name; not dips (too hard), not the banned one
    assert "bench" not in names and "squat" not in names and "treadmill" not in names


def test_add_options_train_a_muscle_the_day_already_trains():
    names = {o.key for o in options_for(PLAN, 3, None, LIBRARY, why_not)}               # Wednesday: row and curl (back, biceps)
    assert names == set()                                                              # the only candidate, lat pulldown, needs equipment
    mon = {o.key for o in options_for(PLAN, 1, None, LIBRARY, why_not)}
    assert {"pushup", "incline"} <= mon and mon.isdisjoint({"bench", "ohp", "lateral", "squat", "dips", "banned", "treadmill"})


def test_a_rest_day_has_no_options_and_a_missing_exercise_is_refused():
    assert options_for(PLAN, 2, None, LIBRARY, why_not) == []
    with pytest.raises(EditRefused):
        options_for(PLAN, 1, 9, LIBRARY, why_not)


@pytest.mark.parametrize("reason,text", [
    ("injury: knee", "it could aggravate your knee"), ("injury: lower_back", "it could aggravate your lower back"),
    ("too hard: advanced", "it is harder than your experience level"),
    ("needs equipment: cable_machine", "you do not have the equipment (cable machine)"),
    ("not a home exercise", "it does not suit where you train"),
])
def test_friendly_reasons(reason, text):
    assert friendly_reason(reason) == text


def sets3(o):
    return 3


def test_options_leave_out_choices_that_would_break_the_weekly_cap():
    add = {o.key for o in options_for(CHEST_HEAVY, 1, None, LIBRARY, why_not, sets3)}
    assert "pushup" not in add and "incline" not in add                  # chest is at 20: more chest sets would be refused
    swap = {o.key for o in options_for(CHEST_HEAVY, 1, 1, LIBRARY, why_not, sets3)}
    assert {"incline", "pushup"} <= swap                                 # replacing a 5-set bench frees room: 20 - 5 + 3
    without_check = {o.key for o in options_for(CHEST_HEAVY, 1, None, LIBRARY, why_not)}
    assert {"pushup", "incline"} <= without_check                        # the cap filter is what removed them


def test_a_main_muscle_that_is_not_chest_is_not_blocked_by_a_full_chest():
    new, _ = add_exercise(CHEST_HEAVY, 1, "curl", **RULES)
    assert keys(new, 1)[-1] == "curl"
