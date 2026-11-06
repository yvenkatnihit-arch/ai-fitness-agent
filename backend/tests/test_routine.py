import itertools

import pytest

from app.calc.routine import Prescription, exercise_kind, next_weight, prescribe
from app.calc.targets import GOAL_ADJUSTMENT
from app.core.vocabulary import PACES
from exercisedata.records import read_exercises
from fooddata.download import DATA_DIR

GOALS = tuple(GOAL_ADJUSTMENT)
LEVELS = ("beginner", "intermediate", "advanced")


def rx(level, goal, pace, pattern, muscles, name):
    return prescribe(level, goal, pace, pattern, muscles, name)


def shape(p):
    """(sets, reps_min, reps_max, rest_sec): the numbers, without the note."""
    return (p.sets, p.reps_min, p.reps_max, p.rest_sec)


# --- Which kind of exercise is it? ---

@pytest.mark.parametrize("pattern,muscles,name,kind", [
    ("squat", ["quads", "glutes"], "Barbell Back Squat", "compound"),
    ("pull_horizontal", ["back", "biceps"], "Seated Cable Row", "compound"),
    ("carry", ["forearms", "traps", "abs"], "Farmer's Carry", "compound"),
    ("pull_horizontal", ["biceps"], "Dumbbell Biceps Curl", "isolation"),
    ("push_vertical", ["shoulders"], "Dumbbell Lateral Raise", "isolation"),
    ("squat", ["calves"], "Standing Calf Raise", "isolation"),
    ("core", ["abs"], "Crunch", "core"),
    ("core", ["abs"], "Plank", "timed"),
    ("hinge", ["lower_back", "glutes"], "Superman Hold", "timed"),
    ("squat", ["quads"], "Wall Sit", "timed"),
    ("cardio", ["full_body"], "Burpee", None),
    ("mobility", ["back"], "Thoracic Rotation", None),
])
def test_exercise_kind(pattern, muscles, name, kind):
    assert exercise_kind(pattern, muscles, name) == kind


# --- Hand-worked prescriptions: sets, reps, rest ---

SQUAT = ("squat", ["quads", "glutes"], "Barbell Back Squat")
CURL = ("pull_horizontal", ["biceps"], "Dumbbell Biceps Curl")


def test_intermediate_muscle_gain_squat():
    assert rx("intermediate", "muscle_gain", "normal", *SQUAT) == Prescription(3, 6, 10, 120, "Stop each set with 2 good reps left in the tank")


def test_advanced_gets_more_sets_and_longer_rest_and_fast_adds_one_set():
    assert shape(rx("advanced", "muscle_gain", "normal", *SQUAT)) == (4, 6, 10, 150)
    assert shape(rx("advanced", "muscle_gain", "fast", *SQUAT)) == (5, 6, 10, 150)     # +1 set, capped at 5
    assert shape(rx("advanced", "muscle_gain", "slow", *SQUAT)) == (3, 6, 10, 150)     # -1 set


def test_beginners_get_the_same_gentle_range_whatever_the_goal_and_never_extra_volume():
    for goal in GOALS:
        assert shape(rx("beginner", goal, "normal", *SQUAT))[1:3] == (8, 12), goal
    assert rx("beginner", "muscle_gain", "fast", *SQUAT).sets == 2                   # fast gives beginners nothing extra
    assert rx("beginner", "muscle_gain", "slow", *SQUAT).sets == 2                   # and never fewer than 2


def test_fat_loss_rests_less_and_uses_higher_reps_on_isolation():
    assert shape(rx("intermediate", "fat_loss", "normal", *SQUAT)) == (3, 8, 12, 90)    # 120 - 30
    assert shape(rx("intermediate", "fat_loss", "normal", *CURL)) == (3, 12, 15, 60)
    assert shape(rx("intermediate", "muscle_gain", "normal", *CURL)) == (3, 10, 15, 60)


def test_fast_adds_a_set_only_to_big_lifts_of_experienced_lifters():
    assert rx("intermediate", "muscle_gain", "fast", *CURL).sets == 3                # isolation: no extra
    assert rx("intermediate", "muscle_gain", "fast", *SQUAT).sets == 4


def test_timed_holds_say_how_long_and_use_one_rep():
    plank = rx("intermediate", "fat_loss", "normal", "core", ["abs"], "Plank")
    assert (plank.sets, plank.reps_min, plank.reps_max, plank.rest_sec, plank.note) == (3, 1, 1, 45, "Hold 30-45 seconds")
    assert rx("beginner", "fat_loss", "normal", "core", ["abs"], "Plank").note == "Hold 20-30 seconds"


def test_cardio_and_mobility_are_not_sets_and_reps():
    assert rx("beginner", "fat_loss", "normal", "cardio", ["full_body"], "Brisk Walk") is None
    assert rx("advanced", "muscle_gain", "fast", "mobility", ["hips"], "Clamshell") is None


@pytest.mark.parametrize("args", [("pro", "fat_loss", "normal"), ("beginner", "bulk", "normal"), ("beginner", "fat_loss", "extreme")])
def test_unknown_level_goal_or_pace_is_refused(args):
    with pytest.raises(ValueError):
        prescribe(*args, "squat", ["quads", "glutes"], "Squat")


def test_every_combination_fits_the_plan_table():
    """sets 1-10, reps 1-50 / max 1-100 with max >= min, rest 0-600, note under 120 characters."""
    examples = [SQUAT, CURL, ("core", ["abs"], "Crunch"), ("core", ["abs"], "Plank")]
    for level, goal, pace, (pattern, muscles, name) in itertools.product(LEVELS, GOALS, PACES, examples):
        p = rx(level, goal, pace, pattern, muscles, name)
        label = (level, goal, pace, name)
        assert 1 <= p.sets <= 10 and 1 <= p.reps_min <= 50 and p.reps_min <= p.reps_max <= 100, label
        assert 0 <= p.rest_sec <= 600 and (p.note is None or len(p.note) <= 120), label


# --- The real library ---

def test_every_strength_exercise_in_our_library_gets_a_valid_prescription():
    library = read_exercises(DATA_DIR / "exercises.csv")
    timed, untimed = [], []
    for ex in library:
        p = prescribe("intermediate", "muscle_gain", "normal", ex.movement_pattern, ex.muscle_groups, ex.name)
        if ex.movement_pattern in ("cardio", "mobility"):
            untimed.append(ex.key)
            assert p is None, ex.key
            continue
        assert p is not None and 2 <= p.sets <= 5 and p.reps_min <= p.reps_max and 30 <= p.rest_sec <= 240, ex.key
        if p.reps_max == 1:
            timed.append(ex.key)
    assert sorted(timed) == ["hollow_body_hold", "plank", "side_plank", "superman_hold", "wall_sit"]
    assert len(untimed) >= 15


# --- Progression ---

BENCH = Prescription(3, 6, 10, 120)


def test_no_history_means_the_user_picks_a_weight_and_we_never_invent_one():
    p = next_weight(None, [], BENCH, "push_horizontal")
    assert (p.action, p.weight_kg) == ("start", None) and "10 reps" in p.reason


def test_every_set_at_the_top_adds_weight_more_for_lower_body():
    upper = next_weight(40, [[10, 10, 10]], BENCH, "push_horizontal")
    assert (upper.action, upper.weight_kg) == ("increase", 42.5)
    lower = next_weight(60, [[10, 10, 10]], BENCH, "squat")
    assert (lower.action, lower.weight_kg) == ("increase", 65.0)


def test_one_set_short_of_the_top_holds_the_weight():
    p = next_weight(40, [[10, 9, 8]], BENCH, "push_horizontal")
    assert (p.action, p.weight_kg) == ("hold", 40) and "10" in p.reason


def test_a_single_bad_session_does_not_cut_the_weight_but_two_in_a_row_do():
    assert next_weight(40, [[5, 4, 4]], BENCH, "push_horizontal").action == "hold"
    assert next_weight(40, [[10, 10, 10], [5, 4, 4]], BENCH, "push_horizontal").action == "hold"
    p = next_weight(40, [[5, 5, 4], [5, 4, 4]], BENCH, "push_horizontal")
    assert (p.action, p.weight_kg) == ("reduce", 36.0)                         # 40 - 10%
    # 42.5 - 10% = 38.25, exactly halfway between 38.0 and 38.5: a reduction rounds DOWN, never heavier than intended.
    assert next_weight(42.5, [[5, 5, 4], [5, 4, 4]], BENCH, "push_horizontal").weight_kg == 38.0
    assert next_weight(100, [[5, 5, 4], [5, 4, 4]], BENCH, "squat").weight_kg == 90.0               # exact, not 89.5


def test_only_the_last_two_sessions_count():
    assert next_weight(40, [[5, 4, 4], [5, 4, 4], [10, 9, 8]], BENCH, "push_horizontal").action == "hold"


def test_bodyweight_exercises_progress_by_difficulty_not_weight():
    up = next_weight(None, [[10, 10, 10]], BENCH, "push_horizontal")
    assert (up.action, up.weight_kg) == ("increase", None) and "harder" in up.reason
    down = next_weight(None, [[3, 3, 2], [3, 2, 2]], BENCH, "push_horizontal")
    assert (down.action, down.weight_kg) == ("reduce", None)


@pytest.mark.parametrize("weight,history", [(-1, [[8]]), (501, [[8]]), (40, [[101]]), (40, [[-1]]), (40, [[8.5]]), (40, [[True]])])
def test_impossible_numbers_are_refused(weight, history):
    with pytest.raises(ValueError):
        next_weight(weight, history, BENCH, "push_horizontal")
