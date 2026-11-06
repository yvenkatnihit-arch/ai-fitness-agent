"""Split inputs from the real database, and whether our real exercise library can fill every split day.
Needs the exercises loaded (`uv run python -m exercisedata.load`)."""

import pytest

from app.calc.exercise_filter import ExerciseNeeds, filter_exercises
from app.calc.splits import CATALOGUE
from app.db import exercises as exercise_repo
from app.db import splits as repo

pytestmark = pytest.mark.db


@pytest.fixture
def user_conn(scratch_user, act_as):
    conn, uid = scratch_user
    conn.execute("update public.profiles set days_per_week = 4, experience_level = 'intermediate' where id = %s", (uid,))
    conn.execute("insert into public.goals (user_id, goal_type, start_weight_kg) values (%s, 'muscle_gain', 70)", (uid,))
    act_as(conn, uid)
    return conn


def test_inputs_come_from_the_training_step_and_the_active_goal(user_conn):
    assert repo.read_split_inputs(user_conn) == repo.SplitInputs(4, "intermediate", "muscle_gain")


def test_missing_training_or_goal_gives_none(scratch_user, act_as):
    conn, uid = scratch_user
    conn.execute("update public.profiles set days_per_week = 4 where id = %s", (uid,))   # no level, no goal
    act_as(conn, uid)
    assert repo.read_split_inputs(conn) is None


def patterns_in_use():
    return sorted({p for split in CATALOGUE for day in split.days for p in day.patterns})


def test_the_gym_library_has_plenty_for_every_pattern_every_split_uses(user_conn):
    library = exercise_repo.list_exercises(user_conn)
    shown = filter_exercises(library, ExerciseNeeds("gym", "advanced", frozenset(), frozenset()))
    for pattern in patterns_in_use():
        assert sum(e.movement_pattern == pattern for e in shown) >= 5, pattern


def test_a_beginner_at_home_with_basic_kit_can_still_fill_every_pattern(user_conn):
    library = exercise_repo.list_exercises(user_conn)
    kit = frozenset({"dumbbells", "bench", "pull_up_bar", "resistance_bands"})
    shown = filter_exercises(library, ExerciseNeeds("home", "beginner", frozenset(), kit))
    for pattern in patterns_in_use():
        assert any(e.movement_pattern == pattern for e in shown), pattern


def test_with_a_bad_knee_every_split_day_still_has_something_for_each_of_its_main_patterns(user_conn):
    """A split day may lose some patterns to an injury (squats), but never all of them."""
    library = exercise_repo.list_exercises(user_conn)
    shown = filter_exercises(library, ExerciseNeeds("gym", "intermediate", frozenset({"knee"}), frozenset()))
    available = {e.movement_pattern for e in shown}
    for split in CATALOGUE:
        for day in split.days:
            assert available & set(day.patterns), (split.key, day.label)
