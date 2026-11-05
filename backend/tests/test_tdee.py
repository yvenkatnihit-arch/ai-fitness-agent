import math

import pytest

from app.calc.bmr import bmr
from app.calc.tdee import ACTIVITY_MULTIPLIERS, tdee

# Expected values worked out by hand: TDEE = BMR * multiplier


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("sedentary", 2136.0),     # 1780 * 1.2
        ("light", 2447.5),         # 1780 * 1.375
        ("moderate", 2759.0),      # 1780 * 1.55
        ("active", 3070.5),        # 1780 * 1.725
        ("very_active", 3382.0),   # 1780 * 1.9
    ],
)
def test_each_activity_level(level, expected):
    assert tdee(1780, level) == pytest.approx(expected)


def test_works_with_bmr_output():
    # Female, 60 kg, 165 cm, 25 y -> BMR 1345.25; light activity -> 1345.25 * 1.375
    assert tdee(bmr(60, 165, 25, "female"), "light") == pytest.approx(1849.71875)


def test_more_activity_always_means_higher_tdee():
    values = [tdee(1500, level) for level in ACTIVITY_MULTIPLIERS]
    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_tdee_is_always_above_bmr():
    # Even sedentary people burn more than their resting rate.
    assert all(tdee(1500, level) > 1500 for level in ACTIVITY_MULTIPLIERS)


def test_rejects_unknown_activity_level():
    with pytest.raises(ValueError):
        tdee(1780, "super_active")


@pytest.mark.parametrize("bad_bmr", [0, -100, math.nan, math.inf, True, "1780", None])
def test_rejects_bad_bmr(bad_bmr):
    with pytest.raises(ValueError):
        tdee(bad_bmr, "moderate")
