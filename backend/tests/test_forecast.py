from datetime import date, timedelta

import pytest

from app.calc.engine import BodyProfile, calculate_targets
from app.calc.forecast import forecast_goal, weekly_change_kg
from app.safety import safety_config as cfg

TODAY = date(2026, 11, 6)
# Male, 80 kg, 180 cm, 30 y, moderate -> TDEE 2759, fat-loss target 2207.2 (a deficit of 551.8 kcal a day).
MAN = BodyProfile(80, 180, 30, "male", "moderate", "fat_loss")


def test_the_weekly_change_is_the_calorie_gap_turned_into_kilograms():
    t = calculate_targets(MAN)
    assert weekly_change_kg(MAN) == pytest.approx((t.calorie_target_kcal - t.tdee_kcal) * 7 / 7700)
    assert weekly_change_kg(MAN) == pytest.approx(-0.5016, abs=0.001)    # 551.8 * 7 / 7700, worked out by hand


def test_a_fat_loss_forecast_by_hand_and_in_order():
    f = forecast_goal(MAN, 75, TODAY)
    assert f.status == "ready" and f.weekly_change_kg == -0.5
    # 5 kg at about 0.5 kg a week is 10 weeks = 70 days; TDEE falls as weight falls so it takes a little longer.
    assert 69 <= (f.earliest - TODAY).days <= 76
    assert f.earliest < f.likely < f.latest
    # 85% and 70% adherence stretch the time by about 1/0.85 and 1/0.70
    assert (f.likely - TODAY).days == pytest.approx((f.earliest - TODAY).days / 0.85, rel=0.06)
    assert (f.latest - TODAY).days == pytest.approx((f.earliest - TODAY).days / 0.70, rel=0.06)
    assert f.weeks_likely == -(-(f.likely - TODAY).days // 7)             # whole weeks, rounded up


def test_a_gain_goal_forecasts_too():
    f = forecast_goal(BodyProfile(70, 175, 25, "male", "moderate", "muscle_gain"), 74, TODAY)
    assert f.status == "ready" and f.weekly_change_kg > 0 and f.earliest < f.likely < f.latest


def test_the_pace_changes_the_date():
    dates = {}
    for pace in ("slow", "normal", "fast"):
        dates[pace] = forecast_goal(BodyProfile(80, 180, 30, "male", "moderate", "fat_loss", pace=pace), 72, TODAY).likely
    assert dates["fast"] < dates["normal"] < dates["slow"]


def test_the_forecast_never_beats_the_weekly_loss_cap():
    heavy = BodyProfile(120, 180, 30, "male", "very_active", "fat_loss", pace="fast")
    f = forecast_goal(heavy, 90, TODAY)
    assert abs(f.weekly_change_kg) <= 120 * cfg.MAX_WEEKLY_LOSS_FRACTION + 1e-9       # at most 1% of body weight a week
    assert (f.earliest - TODAY).days >= 30 / (120 * cfg.MAX_WEEKLY_LOSS_FRACTION) * 7 - 7


def test_eating_disorder_history_gets_no_dates_or_weights():
    f = forecast_goal(BodyProfile(60, 165, 25, "female", "light", "fat_loss", frozenset({"eating_disorder_history"})), 55, TODAY)
    assert f.status == "habits_only" and f.earliest is None and f.target_weight_kg is None


@pytest.mark.parametrize("goal", ["general_fitness", "recomp"])
def test_goals_that_do_not_aim_at_a_weight_have_no_date(goal):
    assert forecast_goal(BodyProfile(80, 180, 30, "male", "moderate", goal), 75, TODAY).status == "no_target"


def test_no_target_weight_means_no_date():
    assert forecast_goal(MAN, None, TODAY).status == "no_target"


def test_already_at_the_target():
    assert forecast_goal(MAN, 80.3, TODAY).status == "already_there"


def test_a_target_on_the_wrong_side_of_the_goal_is_reported_not_forecast():
    assert forecast_goal(MAN, 85, TODAY).status == "wrong_direction"                                     # fat loss, target above
    assert forecast_goal(BodyProfile(70, 175, 25, "male", "moderate", "muscle_gain"), 65, TODAY).status == "wrong_direction"


def test_a_plan_held_up_by_the_calorie_floor_says_so_instead_of_inventing_a_date():
    # Small, sedentary woman: the 1200 kcal floor is above her maintenance, so a "fat loss" plan can't lose weight.
    small = BodyProfile(45, 150, 60, "female", "sedentary", "fat_loss")
    f = forecast_goal(small, 42, TODAY)
    assert f.status == "not_moving" and f.earliest is None


def test_a_very_distant_target_is_called_too_far():
    f = forecast_goal(BodyProfile(150, 190, 30, "male", "sedentary", "fat_loss", pace="slow"), 50, TODAY)
    assert f.status == "too_far" and f.latest is None


def test_dates_are_never_in_the_past_and_within_two_years():
    f = forecast_goal(MAN, 70, TODAY)
    assert f.earliest > TODAY and f.latest <= TODAY + timedelta(days=104 * 7)
