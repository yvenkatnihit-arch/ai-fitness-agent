"""Pace through the whole engine: it moves the target, but the safety clamps still decide the limits."""

import itertools

import pytest

from app.calc.engine import BodyProfile, calculate_targets
from app.safety import safety_config as cfg

# Male, 80 kg, 180 cm, 30 y, moderate: BMR 1780, TDEE 2759.
BASE = dict(weight_kg=80, height_cm=180, age_years=30, sex="male", activity_level="moderate")


def run(pace, goal="fat_loss", flags=frozenset(), **changes):
    return calculate_targets(BodyProfile(**{**BASE, **changes}, goal=goal, screening_flags=flags, pace=pace))


def test_normal_is_exactly_what_it_was_before_pace_existed():
    assert run("normal").calorie_target_kcal == pytest.approx(2207.2)
    assert calculate_targets(BodyProfile(**BASE, goal="fat_loss")).calorie_target_kcal == pytest.approx(2207.2)


def test_fast_and_slow_fat_loss_for_a_healthy_user():
    slow, fast = run("slow"), run("fast")
    assert slow.calorie_target_kcal == pytest.approx(2483.1)    # 2759 * 0.90
    assert fast.calorie_target_kcal == pytest.approx(2069.25)   # 2759 * 0.75: right at the 25% cap, so no clamp reason
    assert fast.reasons == () and slow.reasons == ()
    assert fast.protein_g == slow.protein_g == 160              # protein follows body weight, not pace


def test_fast_with_a_health_flag_is_treated_as_normal_and_says_so():
    held = run("fast", flags=frozenset({"diabetes"}))
    normal = run("normal", flags=frozenset({"diabetes"}))
    assert held.calorie_target_kcal == normal.calorie_target_kcal
    assert held.reasons == ("pace_limited_by_screening", "screening_deficit_cap")  # held back, then the 10% flag cap
    assert held.doctor_note is True


def test_eating_disorder_history_never_gets_a_deficit_whatever_the_pace():
    for pace in ("slow", "normal", "fast"):
        result = run(pace, flags=frozenset({"eating_disorder_history"}))
        assert result.calorie_target_kcal == pytest.approx(result.tdee_kcal), pace
        assert result.focus_on_habits is True


def test_fast_cannot_push_a_gain_goal_past_the_surplus_cap():
    for goal in ("muscle_gain", "weight_gain"):
        result = run("fast", goal=goal)
        assert result.calorie_target_kcal <= result.tdee_kcal * (1 + cfg.MAX_SURPLUS_FRACTION) + 1e-9, goal


def test_a_fast_goal_for_someone_with_a_big_tdee_is_still_held_to_the_weekly_loss_cap():
    # Light but very active: 25% of a large TDEE would exceed 1% of body weight a week.
    result = calculate_targets(BodyProfile(60, 185, 22, "male", "very_active", "fat_loss", pace="fast"))
    max_daily_deficit = 60 * cfg.MAX_WEEKLY_LOSS_FRACTION * cfg.KCAL_PER_KG_FAT / 7
    assert result.tdee_kcal - result.calorie_target_kcal <= max_daily_deficit + 1e-9
    assert "weekly_loss_rate_cap" in result.reasons


def test_no_combination_of_inputs_ever_breaks_a_safety_limit():
    people = [(45, 150, "female", "sedentary"), (60, 185, "male", "very_active"), (80, 180, "male", "moderate"),
              (120, 175, "other", "light"), (200, 190, "male", "active")]
    flag_sets = [frozenset(), frozenset({"diabetes"}), frozenset({"eating_disorder_history"}),
                 frozenset({"pregnant_or_breastfeeding", "kidney"})]
    goals = ("fat_loss", "muscle_gain", "weight_gain", "recomp", "general_fitness")
    for (weight, height, sex, activity), flags, goal, pace in itertools.product(
        people, flag_sets, goals, ("slow", "normal", "fast")
    ):
        t = calculate_targets(BodyProfile(weight, height, 35, sex, activity, goal, flags, pace))
        label = (weight, sex, sorted(flags), goal, pace)
        assert t.calorie_target_kcal >= cfg.calorie_floor(sex) - 1e-9, label
        assert t.calorie_target_kcal <= t.tdee_kcal * (1 + cfg.MAX_SURPLUS_FRACTION) + 1e-9, label
        assert t.calorie_target_kcal >= t.tdee_kcal * (1 - cfg.max_deficit_fraction(set(flags))) - 1e-9 or \
            t.calorie_target_kcal == cfg.calorie_floor(sex), label
        assert t.tdee_kcal - t.calorie_target_kcal <= max(
            weight * cfg.MAX_WEEKLY_LOSS_FRACTION * cfg.KCAL_PER_KG_FAT / 7, t.tdee_kcal - cfg.calorie_floor(sex)
        ) + 1e-9, label
