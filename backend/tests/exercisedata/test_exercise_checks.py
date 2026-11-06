from dataclasses import replace

import pytest

from exercisedata import build
from exercisedata.checks import check_cues, check_exercise, check_library, check_location, required_injury_tags
from exercisedata.freedb import ExerciseRef, default_path, read_free_exercise_db
from exercisedata.records import Exercise, read_exercises

GOOD = Exercise(
    key="bodyweight_squat", name="Bodyweight Squat", muscle_groups=("quads", "glutes"), equipment=(), location="both",
    difficulty="beginner", movement_pattern="squat",
    cues=("Feet shoulder-width and toes slightly out", "Sit back and down with your chest up"),
    contraindications=("knee",), ref_id="", reviewed_by="", note="",
)
CITED = replace(GOOD, ref_id="Bodyweight_Squat")   # a row that cites a Free Exercise DB entry
REF = ExerciseRef("Bodyweight_Squat", "Bodyweight Squat", "beginner", "body only", ("quadriceps",), ("glutes",), "strength")


def messages(issues, severity=None):
    return [i.message for i in issues if severity in (None, i.severity)]


def test_a_good_row_has_no_issues():
    assert check_exercise(GOOD, REF) == []


@pytest.mark.parametrize("change,fragment", [
    ({"muscle_groups": ("biceps", "wings")}, "unknown muscle group 'wings'"),
    ({"equipment": ("trampoline",)}, "unknown equipment"),
    ({"location": "outside"}, "unknown location"),
    ({"difficulty": "pro"}, "unknown difficulty"),
    ({"movement_pattern": "dance"}, "unknown movement pattern"),
    ({"contraindications": ("knee", "knee")}, "listed twice"),
    ({"contraindications": ("knee", "toe")}, "unknown injury tag 'toe'"),
    ({"key": "Bad Key"}, "lower_snake_case"),
    ({"muscle_groups": ()}, "at least one muscle group"),
])
def test_vocabulary_errors(change, fragment):
    assert any(fragment in m for m in messages(check_exercise(replace(GOOD, **change), None), "error"))


def test_cue_count_length_and_total():
    assert "needs 2-4" in messages(check_cues(replace(GOOD, cues=("Only one cue is not enough",))))[0]
    assert "needs 2-4" in messages(check_cues(replace(GOOD, cues=("Cue number one here",) * 5)))[0]
    assert "characters" in messages(check_cues(replace(GOOD, cues=("Short", "A fine cue that is long enough"))))[0]
    long_cues = tuple("x" * 109 for _ in range(4))  # each cue is fine but the total passes 400
    assert any("database limit" in m for m in messages(check_cues(replace(GOOD, cues=long_cues))))


def test_gym_machines_must_be_gym_only():
    assert check_location(replace(GOOD, equipment=("cable_machine",), location="both"))
    assert check_location(replace(GOOD, equipment=("cable_machine",), location="gym")) == []
    assert check_location(replace(GOOD, equipment=("dumbbells",), location="both")) == []


@pytest.mark.parametrize("name,pattern,expected", [
    ("Bodyweight Squat", "squat", {"knee"}),
    ("Barbell Back Squat", "squat", {"knee", "lower_back"}),
    ("Leg Press", "squat", {"knee", "lower_back"}),
    ("Romanian Deadlift", "hinge", {"lower_back"}),
    ("Push-Up", "push_horizontal", {"shoulder", "wrist"}),
    ("Pull-Up", "pull_vertical", {"shoulder", "elbow"}),
    ("Jump Rope", "cardio", {"knee", "ankle"}),
    ("Burpee", "cardio", {"knee", "ankle"}),
    ("Crunch", "core", {"neck"}),
    ("Russian Twist", "core", {"lower_back"}),
    ("Dumbbell Biceps Curl", "pull_horizontal", {"elbow"}),
    ("Plank", "core", {"wrist"}),
    ("Treadmill Run", "cardio", {"knee", "ankle"}),
    ("Child's Pose", "mobility", set()),
    ("Dead Bug", "core", set()),
])
def test_required_injury_tags(name, pattern, expected):
    assert set(required_injury_tags(replace(GOOD, name=name, movement_pattern=pattern))) == expected


def test_leg_and_hamstring_curls_are_not_elbow_exercises():
    assert "elbow" not in required_injury_tags(replace(GOOD, name="Hamstring Curl", movement_pattern="hinge"))
    assert "elbow" not in required_injury_tags(replace(GOOD, name="Leg Curl", movement_pattern="hinge"))


def test_missing_required_tag_is_an_error_naming_the_reason():
    row = replace(GOOD, name="Jump Rope", movement_pattern="cardio", contraindications=("knee",))
    assert any("'ankle'" in m and "jumping" in m for m in messages(check_exercise(row, None), "error"))


def test_reference_comparison():
    assert check_exercise(CITED, REF) == []                                                    # all agree
    assert check_exercise(replace(GOOD, ref_id="Nope"), None)[0].severity == "error"          # id not found
    assert "Free Exercise DB says advanced" in messages(check_exercise(CITED, replace(REF, level="advanced")))[0]
    assert "equipment" in messages(check_exercise(replace(CITED, equipment=("dumbbells",), location="both"), REF))[0]
    assert "we list no equipment" in messages(check_exercise(CITED, replace(REF, equipment="barbell")))[0]
    assert "main muscle" in messages(check_exercise(CITED, replace(REF, primary_muscles=("biceps",), secondary_muscles=())))[0]
    assert check_exercise(CITED, replace(REF, equipment=None)) == []   # unknown equipment on their side is fine
    assert check_exercise(GOOD, replace(REF, level="advanced")) == []  # no ref cited: nothing is compared


def test_duplicate_key_and_name_are_errors():
    other = replace(GOOD, key="other", name="BODYWEIGHT SQUAT")
    found = messages(check_library([GOOD, other, replace(GOOD, name="Another")]))
    assert any("key 'bodyweight_squat'" in m for m in found) and any("name 'bodyweight squat'" in m for m in found)


def test_status_stays_review_until_someone_signs_off():
    assert build.Reviewed(GOOD).status == "review"
    assert build.Reviewed(replace(GOOD, reviewed_by="Venkat")).status == "ready"
    bad = build.Reviewed(replace(GOOD, reviewed_by="Venkat"), check_exercise(replace(GOOD, difficulty="pro"), None))
    assert bad.status == "blocked"


def test_coverage_notes_name_the_gaps():
    notes = build.coverage_notes([GOOD])
    assert any("'hinge'" in n for n in notes) and any("biceps" in n for n in notes)


def test_our_real_library_has_no_errors():
    exercises = read_exercises(build.EXERCISES)
    refs = {r.id: r for r in read_free_exercise_db(default_path())} if default_path().exists() else {}
    if not refs:
        pytest.skip("Free Exercise DB not downloaded (uv run python -m fooddata.download)")
    blocked = [(r.exercise.key, messages(r.issues, "error")) for r in build.review_all(exercises, refs) if r.status == "blocked"]
    assert blocked == []
    assert 80 <= len(exercises) <= 130                                        # brief: roughly 80-120
    assert all(2 <= len(e.cues) <= 4 for e in exercises)
