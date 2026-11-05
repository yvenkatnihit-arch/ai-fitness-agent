import itertools

import pytest

from app.calc import macros as m
from app.calc.macros import macros
from app.calc.targets import GOAL_ADJUSTMENT


def kcal_of(result):
    return result.protein_g * 4 + result.carbs_g * 4 + result.fat_g * 9


# --- Hand-worked examples ---

def test_fat_loss_male_80kg():
    # protein 80 * 2.0 = 160 g (640 kcal, 29% of 2207.2: under the 35% cap)
    # fat     2207.2 * 0.25 / 9 = 61.31 g (551.8 kcal)
    # carbs   (2207.2 - 640 - 551.8) / 4 = 253.85 g
    result = macros(2207.2, 80, "fat_loss", set())
    assert result.protein_g == pytest.approx(160)
    assert result.fat_g == pytest.approx(61.3111, rel=1e-4)
    assert result.carbs_g == pytest.approx(253.85)
    assert result.reasons == ()


def test_kidney_flag_caps_protein_at_0_8_g_per_kg():
    # protein 80 * 0.8 = 64 g; carbs (2207.2 - 256 - 551.8) / 4 = 349.85 g
    result = macros(2207.2, 80, "fat_loss", {"kidney"})
    assert result.protein_g == pytest.approx(64)
    assert result.carbs_g == pytest.approx(349.85)
    assert result.reasons == (m.KIDNEY_PROTEIN_CAP,)


def test_other_flags_do_not_change_protein():
    assert macros(2207.2, 80, "fat_loss", {"diabetes"}).protein_g == pytest.approx(160)


def test_heavy_user_protein_capped_at_35_percent_of_calories():
    # 140 * 2.0 = 280 g (1120 kcal = 43%) -> cap 2600 * 0.35 / 4 = 227.5 g
    # fat 650 / 9 = 72.22 g; carbs (2600 - 910 - 650) / 4 = 260 g
    result = macros(2600, 140, "fat_loss", set())
    assert result.protein_g == pytest.approx(227.5)
    assert result.carbs_g == pytest.approx(260)
    assert result.reasons == (m.PROTEIN_CALORIE_CAP,)


@pytest.mark.parametrize(
    ("goal", "g_per_kg"),
    [("fat_loss", 2.0), ("recomp", 2.0), ("muscle_gain", 1.8), ("weight_gain", 1.6), ("general_fitness", 1.6)],
)
def test_protein_per_kg_by_goal(goal, g_per_kg):
    assert macros(2800, 70, goal, set()).protein_g == pytest.approx(70 * g_per_kg)


def test_every_goal_has_a_protein_value():
    assert set(m.PROTEIN_G_PER_KG) == set(GOAL_ADJUSTMENT)


# --- Properties that must hold for any input ---

@pytest.mark.parametrize(
    ("kcal", "weight", "goal", "flags"),
    list(
        itertools.product(
            [1200, 1800, 2500, 3500],
            [45, 80, 140, 300],
            list(m.PROTEIN_G_PER_KG),
            [frozenset(), frozenset({"kidney"}), frozenset({"kidney", "diabetes"})],
        )
    ),
)
def test_macros_always_add_up_and_respect_limits(kcal, weight, goal, flags):
    result = macros(kcal, weight, goal, set(flags))

    assert kcal_of(result) == pytest.approx(kcal)              # adds up to the target
    assert result.fat_g * 9 == pytest.approx(kcal * 0.25)      # fat is 25%
    assert result.protein_g * 4 <= kcal * 0.35 + 1e-9          # protein <= 35%
    assert result.carbs_g * 4 >= kcal * 0.40 - 1e-9           # so carbs are >= 40%
    if "kidney" in flags:
        assert result.protein_g <= weight * 0.8 + 1e-9


# --- Bad inputs ---

def test_rejects_unknown_goal():
    with pytest.raises(ValueError):
        macros(2200, 80, "bulk", set())


def test_rejects_unknown_flag():
    with pytest.raises(ValueError):
        macros(2200, 80, "fat_loss", {"kidny"})


@pytest.mark.parametrize(("kcal", "weight"), [(0, 80), (2200, 20), (2200, True), ("2200", 80)])
def test_rejects_bad_numbers(kcal, weight):
    with pytest.raises(ValueError):
        macros(kcal, weight, "fat_loss", set())
