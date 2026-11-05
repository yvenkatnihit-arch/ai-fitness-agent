import math

import pytest

from app.calc.bmr import bmr
from app.calc.targets import GOAL_ADJUSTMENT, calorie_target
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


def test_defaults_stay_within_safety_caps():
    # The goal defaults must never ask for more than safety_config allows.
    for goal, adjustment in GOAL_ADJUSTMENT.items():
        assert -cfg.MAX_DEFICIT_FRACTION <= adjustment <= cfg.MAX_SURPLUS_FRACTION, goal


def test_rejects_unknown_goal():
    with pytest.raises(ValueError):
        calorie_target(2759, "bulk")


@pytest.mark.parametrize("bad_tdee", [0, -1, math.nan, True, "2759"])
def test_rejects_bad_tdee(bad_tdee):
    with pytest.raises(ValueError):
        calorie_target(bad_tdee, "fat_loss")
