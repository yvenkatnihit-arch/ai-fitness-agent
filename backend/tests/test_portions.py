import pytest

from app.calc.portions import Nutrition, Per100g, PortionError, grams_for, nutrition_for, total

ROTI = Per100g(kcal=202, protein_g=7.3, carbs_g=39.8, fat_g=1.0)
ROTI_UNITS = {"piece": 43.0}


def test_grams_from_a_household_unit():
    assert grams_for(2, "piece", ROTI_UNITS) == 86.0
    assert grams_for(1.5, "katori", {"katori": 152.8}) == 229.2


def test_grams_typed_directly():
    assert grams_for(120, "g", {}) == 120


def test_unit_the_food_does_not_have_is_refused_with_the_choices():
    with pytest.raises(PortionError, match="use one of: g, piece"):
        grams_for(1, "katori", ROTI_UNITS)


@pytest.mark.parametrize(("quantity", "unit"), [(0, "g"), (-1, "piece"), (3001, "g"), (100, "piece")])
def test_impossible_amounts_are_refused(quantity, unit):
    with pytest.raises(PortionError):
        grams_for(quantity, unit, ROTI_UNITS)  # 100 roti = 4300 g is over the 3000 g item limit


def test_nutrition_scales_per_100g_values():
    # 86 g roti: 202 x 0.86 = 173.72 -> 173.7 kcal
    assert nutrition_for(86, ROTI) == Nutrition(kcal=173.7, protein_g=6.3, carbs_g=34.2, fat_g=0.9)


def test_totals_add_the_rounded_item_values():
    items = [Nutrition(173.7, 6.3, 34.2, 0.9), Nutrition(155.6, 9.1, 19.9, 4.6)]
    assert total(items) == Nutrition(329.3, 15.4, 54.1, 5.5)
    assert total([]) == Nutrition(0, 0, 0, 0)
