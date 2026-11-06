from dataclasses import replace

import pytest

from app.calc.exercise_filter import ExerciseNeeds, ExerciseOption, filter_exercises, setting_for, why_hidden

BASE = ExerciseOption(
    id=1, key="bodyweight_squat", name="Bodyweight Squat", muscle_groups=("quads",), equipment=(), location="both",
    difficulty="beginner", movement_pattern="squat", form_cues=("a", "b"), contraindications=("knee",),
    review_status="review",
)
GYM = ExerciseNeeds("gym", "advanced", frozenset(), frozenset())
HOME = ExerciseNeeds("home", "advanced", frozenset(), frozenset())


def test_a_matching_exercise_is_shown():
    assert why_hidden(BASE, GYM) is None and why_hidden(BASE, HOME) is None


def test_reported_injury_hides_tagged_exercises_only():
    knee = replace(GYM, injuries=frozenset({"knee"}))
    assert why_hidden(BASE, knee) == "injury: knee"
    assert why_hidden(replace(BASE, contraindications=("shoulder",)), knee) is None
    assert why_hidden(replace(BASE, contraindications=()), knee) is None        # untagged is shown


def test_every_reported_injury_counts():
    needs = replace(GYM, injuries=frozenset({"wrist", "lower_back"}))
    option = replace(BASE, contraindications=("lower_back", "wrist", "knee"))
    assert why_hidden(option, needs) == "injury: lower_back, wrist"


@pytest.mark.parametrize("level,difficulty,hidden", [
    ("beginner", "beginner", False), ("beginner", "intermediate", True), ("beginner", "advanced", True),
    ("intermediate", "advanced", True), ("intermediate", "beginner", False), ("advanced", "advanced", False),
])
def test_experience_level(level, difficulty, hidden):
    reason = why_hidden(replace(BASE, contraindications=(), difficulty=difficulty), replace(GYM, level=level))
    assert (reason is not None) is hidden


def test_place_rules():
    assert why_hidden(replace(BASE, location="gym"), HOME) == "not a home exercise"
    assert why_hidden(replace(BASE, location="home"), GYM) == "not a gym exercise"
    assert why_hidden(replace(BASE, location="gym"), GYM) is None
    assert why_hidden(replace(BASE, location="home"), HOME) is None


def test_home_needs_owned_equipment_but_gym_assumes_everything():
    dumbbell = replace(BASE, equipment=("dumbbells", "bench"))
    assert why_hidden(dumbbell, replace(HOME, owned_equipment=frozenset({"dumbbells"}))) == "needs equipment: bench"
    assert why_hidden(dumbbell, replace(HOME, owned_equipment=frozenset({"dumbbells", "bench", "yoga_mat"}))) is None
    assert why_hidden(dumbbell, GYM) is None            # gym: equipment is not checked
    assert why_hidden(replace(BASE, equipment=()), HOME) is None   # bodyweight needs nothing


def test_injury_is_reported_before_other_reasons():
    option = replace(BASE, difficulty="advanced", location="gym")
    assert why_hidden(option, ExerciseNeeds("home", "beginner", frozenset({"knee"}), frozenset())) == "injury: knee"


def test_filter_keeps_order_and_drops_hidden():
    a, b, c = (replace(BASE, id=i, key=f"k{i}", contraindications=tags)
               for i, tags in ((1, ()), (2, ("knee",)), (3, ("shoulder",))))
    needs = replace(GYM, injuries=frozenset({"knee"}))
    assert [e.id for e in filter_exercises([a, b, c], needs)] == [1, 3]


@pytest.mark.parametrize("location,requested,expected", [
    ("gym", None, "gym"), ("home", None, "home"), ("both", None, "gym"),
    ("both", "home", "home"), ("gym", "home", "home"),
])
def test_setting_defaults_and_overrides(location, requested, expected):
    assert setting_for(location, requested) == expected
