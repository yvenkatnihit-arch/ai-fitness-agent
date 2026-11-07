"""How many exercises fit in the time the user has (hand-checked against the routine rules, D-049)."""

import pytest

from app.calc.session_time import (
    DEFAULT_SESSION_MINUTES, SESSION_MINUTES, estimate_day_minutes, exercise_seconds, exercises_for_session,
)


def test_one_exercise_is_its_sets_work_plus_rest_plus_setup():
    # 3 sets x (40 s work + 120 s rest) + 30 s setup = 510 s
    assert exercise_seconds(3, 120) == 510
    assert exercise_seconds(2, 90) == 2 * 130 + 30


@pytest.mark.parametrize("level,expected", [          # muscle gain, normal pace, for 30 / 45 / 60 / 90 minutes
    ("beginner", [5, 5, 5, 5]),                       # 2 sets each, so even 30 minutes fits 5; capped at 5 for beginners
    ("intermediate", [3, 6, 7, 7]),
    ("advanced", [3, 4, 6, 8]),                       # 4 sets and long rests: 30 minutes is only the minimum of 3
])
def test_exercises_by_session_length(level, expected):
    assert [exercises_for_session(level, "muscle_gain", "normal", m) for m in SESSION_MINUTES] == expected


def test_intermediate_hand_check_for_45_minutes():
    # budget (45-5) x 60 = 2400 s. compound 510, compound 510, isolation 3x100+30=330, isolation 330,
    # core 3x85+30=285, isolation 330 -> 2295 fits; the 7th (compound, 510) would make 2805 > 2400.
    assert exercises_for_session("intermediate", "muscle_gain", "normal", 45) == 6


def test_more_time_never_means_fewer_exercises():
    for level in ("beginner", "intermediate", "advanced"):
        for goal in ("fat_loss", "muscle_gain", "recomp"):
            for pace in ("slow", "normal", "fast"):
                counts = [exercises_for_session(level, goal, pace, m) for m in SESSION_MINUTES]
                assert counts == sorted(counts), (level, goal, pace, counts)
                assert all(3 <= c <= 8 for c in counts)


def test_shorter_rest_for_fat_loss_fits_more_in_the_same_time():
    assert exercises_for_session("intermediate", "fat_loss", "normal", 45) >= exercises_for_session("intermediate", "muscle_gain", "normal", 45)


def test_no_answer_means_the_default_of_60():
    assert DEFAULT_SESSION_MINUTES == 60
    assert exercises_for_session("intermediate", "muscle_gain", "normal", None) == exercises_for_session("intermediate", "muscle_gain", "normal", 60)


@pytest.mark.parametrize("bad", [0, 20, 50, 120, -30])
def test_other_lengths_are_refused(bad):
    with pytest.raises(ValueError):
        exercises_for_session("beginner", "fat_loss", "normal", bad)


def test_estimated_day_minutes_rounds_to_five():
    # warm-up 300 s + 6 exercises (3 sets, 90 s rest): 6 x (3 x 130 + 30) = 2520 -> 2820 s = 47 min -> 45
    assert estimate_day_minutes([(3, 90)] * 6) == 45
    assert estimate_day_minutes([]) == 5
