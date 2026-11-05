import itertools

import pytest

from app.calc.macros import calorie_shares, macros


def test_hand_worked_example():
    # 116 g protein = 464 kcal, 148 g carbs = 592 kcal, 39 g fat = 351 kcal; total 1407 kcal
    # exact: 32.98%, 42.08%, 24.95% -> floor 32, 42, 24 (=98) -> +1 to the two biggest remainders
    assert calorie_shares(116, 148, 39) == (33, 42, 25)


def test_plain_rounding_would_give_101_but_this_gives_100():
    # Exact shares 32.6 / 42.6 / 24.8 would round to 33 + 43 + 25 = 101.
    protein_kcal, carbs_kcal, fat_kcal = 326, 426, 248  # out of 1000
    shares = calorie_shares(protein_kcal / 4, carbs_kcal / 4, fat_kcal / 9)
    assert sum(shares) == 100
    # Floors 32 + 42 + 24 = 98, so 2 points go to the biggest remainders: fat (.8), then
    # protein (.6, first of the two .6 ties).
    assert shares == (33, 42, 25)


def test_engine_output_shares_match_our_macro_rules():
    # Fat is always 25% of calories (D-023); protein never above 35%.
    m = macros(2207.2, 80, "fat_loss", set())
    protein, carbs, fat = calorie_shares(m.protein_g, m.carbs_g, m.fat_g)
    assert fat == 25
    assert protein <= 35
    assert protein + carbs + fat == 100


@pytest.mark.parametrize(
    ("protein", "carbs", "fat"),
    list(itertools.product([0, 1, 33.3, 64, 116, 227.5], [0, 2, 99.9, 148, 512.2], [0, 3, 39, 46.24, 92.47])),
)
def test_always_adds_up_to_100(protein, carbs, fat):
    if protein == carbs == fat == 0:
        pytest.skip("covered by the zero test")
    shares = calorie_shares(protein, carbs, fat)
    assert sum(shares) == 100
    assert all(0 <= s <= 100 for s in shares)


def test_zero_calories_is_rejected():
    with pytest.raises(ValueError):
        calorie_shares(0, 0, 0)


@pytest.mark.parametrize("bad", [-1, float("nan"), True, "10"])
def test_bad_numbers_are_rejected(bad):
    with pytest.raises(ValueError):
        calorie_shares(bad, 100, 40)
