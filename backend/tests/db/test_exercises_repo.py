"""Exercise reading and filtering against the real library, as a scratch user (always rolled back).
Needs the exercises loaded (`uv run python -m exercisedata.load`)."""

import pytest

from app.calc.exercise_filter import ExerciseNeeds, filter_exercises
from app.db import exercises as repo

pytestmark = pytest.mark.db


@pytest.fixture
def user_conn(scratch_user, act_as):
    conn, uid = scratch_user
    conn.execute("update public.profiles set experience_level = 'beginner', workout_location = 'home', "
                 "equipment = '{dumbbells}' where id = %s", (uid,))
    conn.execute("insert into public.health_screening (user_id, injury_areas) values (%s, '{knee}')", (uid,))
    act_as(conn, uid)
    return conn


def test_training_context_reads_onboarding_answers(user_conn):
    assert repo.read_training_context(user_conn) == repo.TrainingContext(
        "beginner", "home", frozenset({"dumbbells"}), frozenset({"knee"}))


def test_missing_injury_answers_mean_not_ready_rather_than_no_injuries(scratch_user, act_as):
    conn, uid = scratch_user
    conn.execute("update public.profiles set experience_level = 'beginner', workout_location = 'gym' where id = %s", (uid,))
    act_as(conn, uid)                       # no health_screening row
    assert repo.read_training_context(conn) is None


def test_the_real_library_is_readable_and_split_into_cue_lines(user_conn):
    library = repo.list_exercises(user_conn)
    assert len(library) >= 100
    assert all(2 <= len(e.form_cues) <= 4 for e in library)
    assert next(e for e in library if e.key == "plank").equipment == ()


def test_knee_injury_beginner_at_home_with_dumbbells(user_conn):
    context = repo.read_training_context(user_conn)
    needs = ExerciseNeeds("home", context.level, context.injuries, context.equipment)
    shown = filter_exercises(repo.list_exercises(user_conn), needs)
    assert shown
    assert all("knee" not in e.contraindications for e in shown)                  # injury
    assert all(e.difficulty == "beginner" for e in shown)                         # level
    assert all(e.location in ("home", "both") for e in shown)                     # place
    assert all(set(e.equipment) <= {"dumbbells"} for e in shown)                  # equipment
    keys = {e.key for e in shown}
    assert {"dumbbell_biceps_curl", "plank", "dead_bug"} <= keys
    assert not keys & {"bodyweight_squat", "barbell_back_squat", "leg_press", "bench_dip"}


def test_every_single_injury_still_leaves_a_workable_library(user_conn):
    library = repo.list_exercises(user_conn)
    for injury in ("knee", "lower_back", "shoulder", "wrist", "elbow", "neck", "hip", "ankle"):
        shown = filter_exercises(library, ExerciseNeeds("gym", "advanced", frozenset({injury}), frozenset()))
        assert len(shown) >= 50, injury
        assert {e.movement_pattern for e in shown} >= {"core", "cardio", "mobility"}, injury
