import math

import pytest

from app.calc.bmr import bmr
from app.calc.targets import GOAL_ADJUSTMENT, calorie_target, effective_pace
from app.calc.tdee import tdee
from app.safety import safety_config as cfg

# Expected values worked out by hand: target = TDEE * (1 + adjustment), TDEE = 2759


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        ("fat_loss", 2207.2),         # 2759 * 0.80
        ("muscle_gain", 2979.72),     # 2759 * 1.08
        ("weight_gain", 3034.9),      # 2759 * 1.10
        ("recomp", 2483.1),           # 2759 * 0.90
        ("general_fitness", 2759.0),  # 2759 * 1.00
    ],
)
def test_each_goal(goal, expected):
    assert calorie_target(2759, goal) == pytest.approx(expected)


def test_full_chain_bmr_to_target():
    # Male, 80 kg, 180 cm, 30 y -> BMR 1780 -> moderate TDEE 2759 -> fat loss 2207.2
    assert calorie_target(tdee(bmr(80, 180, 30, "male"), "moderate"), "fat_loss") == pytest.approx(2207.2)


def test_loss_goals_are_below_tdee_and_gain_goals_above():
    assert calorie_target(2500, "fat_loss") < 2500
    assert calorie_target(2500, "recomp") < 2500
    assert calorie_target(2500, "general_fitness") == 2500
    assert calorie_target(2500, "muscle_gain") > 2500
    assert calorie_target(2500, "weight_gain") > 2500


def test_every_pace_stays_within_safety_caps():
    # Not even "fast" may ask for more than safety_config allows.
    for goal, by_pace in GOAL_ADJUSTMENT.items():
        assert set(by_pace) == {"slow", "normal", "fast"}, goal
        for pace, adjustment in by_pace.items():
            assert -cfg.MAX_DEFICIT_FRACTION <= adjustment <= cfg.MAX_SURPLUS_FRACTION, (goal, pace)


# TDEE 2759 again, worked out by hand for every goal and pace.
@pytest.mark.parametrize(
    ("goal", "pace", "expected"),
    [
        ("fat_loss", "slow", 2483.1),         # * 0.90
        ("fat_loss", "normal", 2207.2),       # * 0.80
        ("fat_loss", "fast", 2069.25),        # * 0.75 (the deficit cap)
        ("muscle_gain", "slow", 2869.36),     # * 1.04
        ("muscle_gain", "fast", 3034.9),      # * 1.10 (the surplus cap)
        ("weight_gain", "slow", 2896.95),     # * 1.05
        ("weight_gain", "fast", 3034.9),      # normal is already at the cap, so fast is the same
        ("recomp", "slow", 2621.05),          # * 0.95
        ("recomp", "fast", 2345.15),          # * 0.85
        ("general_fitness", "slow", 2759.0),
        ("general_fitness", "fast", 2759.0),  # maintenance has no pace
    ],
)
def test_pace_changes_the_target_by_hand_calculated_amounts(goal, pace, expected):
    assert calorie_target(2759, goal, pace) == pytest.approx(expected)


def test_faster_means_a_bigger_change_in_the_goal_direction():
    for goal in ("fat_loss", "recomp"):
        slow, normal, fast = (calorie_target(2500, goal, p) for p in ("slow", "normal", "fast"))
        assert slow > normal > fast, goal            # eats less the faster you go
    for goal in ("muscle_gain", "weight_gain"):
        slow, normal, fast = (calorie_target(2500, goal, p) for p in ("slow", "normal", "fast"))
        assert slow < normal <= fast, goal           # eats more the faster you go


def test_pace_defaults_to_normal_and_unknown_pace_is_refused():
    assert calorie_target(2759, "fat_loss") == calorie_target(2759, "fat_loss", "normal")
    for bad in ("extreme", "FAST", None, 1):
        with pytest.raises(ValueError):
            calorie_target(2759, "fat_loss", bad)


def test_health_flags_hold_fast_back_to_normal():
    assert effective_pace("fast", "fat_loss", frozenset({"diabetes"})) == ("normal", True)
    assert effective_pace("fast", "fat_loss", {"eating_disorder_history"}) == ("normal", True)
    assert effective_pace("fast", "fat_loss", frozenset()) == ("fast", False)           # healthy: allowed
    assert effective_pace("slow", "fat_loss", frozenset({"diabetes"})) == ("slow", False)  # slower is never held back
    assert effective_pace("fast", "general_fitness", frozenset({"diabetes"})) == ("normal", False)  # nothing to report


def test_rejects_unknown_goal():
    with pytest.raises(ValueError):
        calorie_target(2759, "bulk")


@pytest.mark.parametrize("bad_tdee", [0, -1, math.nan, True, "2759"])
def test_rejects_bad_tdee(bad_tdee):
    with pytest.raises(ValueError):
        calorie_target(bad_tdee, "fat_loss")
