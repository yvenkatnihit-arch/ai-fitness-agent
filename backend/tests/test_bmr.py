import math

import pytest

from app.calc.bmr import bmr

# Expected values worked out by hand:
#   BMR = 10*weight + 6.25*height - 5*age + s


def test_male():
    # 10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5
    assert bmr(80, 180, 30, "male") == pytest.approx(1780.0)


def test_female():
    # 10*60 + 6.25*165 - 5*25 - 161 = 600 + 1031.25 - 125 - 161
    assert bmr(60, 165, 25, "female") == pytest.approx(1345.25)


def test_other_uses_average_constant():
    # 10*70 + 6.25*170 - 5*40 - 78 = 700 + 1062.5 - 200 - 78
    assert bmr(70, 170, 40, "other") == pytest.approx(1484.5)


def test_other_sits_exactly_halfway_between_male_and_female():
    male = bmr(70, 170, 40, "male")
    female = bmr(70, 170, 40, "female")
    assert bmr(70, 170, 40, "other") == pytest.approx((male + female) / 2)


def test_male_and_female_differ_by_166_kcal():
    # Same body, only the sex constant changes: 5 - (-161) = 166.
    assert bmr(70, 170, 40, "male") - bmr(70, 170, 40, "female") == pytest.approx(166)


def test_each_extra_year_lowers_bmr_by_5():
    assert bmr(70, 170, 31, "male") - bmr(70, 170, 30, "male") == pytest.approx(-5)


def test_boundary_values_are_allowed():
    # The edges of each range are valid inputs.
    assert bmr(30, 120, 18, "female") > 0
    assert bmr(300, 230, 100, "male") > 0


@pytest.mark.parametrize(
    ("weight", "height", "age", "reason"),
    [
        (80, 180, 17, "under 18"),
        (80, 180, 101, "over 100"),
        (29.9, 180, 30, "weight too low"),
        (301, 180, 30, "weight too high"),
        (80, 1.8, 30, "height typed in metres"),
        (80, 231, 30, "height too high"),
        (-80, 180, 30, "negative weight"),
        (math.nan, 180, 30, "NaN weight"),
        (math.inf, 180, 30, "infinite weight"),
        (80, 180, True, "bool age"),
        (80, "180", 30, "height as text"),
    ],
)
def test_rejects_bad_inputs(weight, height, age, reason):
    with pytest.raises(ValueError):
        bmr(weight, height, age, "male")


def test_rejects_unknown_sex():
    with pytest.raises(ValueError):
        bmr(80, 180, 30, "M")
