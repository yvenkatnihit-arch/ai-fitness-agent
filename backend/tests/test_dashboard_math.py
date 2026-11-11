"""Step 8.1 (D-105): the dashboard's arithmetic is plain code. Offline."""

import pytest

from app.workflows.dashboard import percent_of, progress_for, totals_of


@pytest.mark.parametrize("eaten, target, expected", [(0, 1800, 0), (900, 1800, 50), (1800, 1800, 100), (2700, 1800, 150), (1000, 3000, 33), (5, 0, 0)])
def test_percent_of_target(eaten, target, expected):
    assert percent_of(eaten, target) == expected


def test_a_day_without_logs_has_zero_everywhere():
    assert totals_of([]) == {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}


def test_totals_add_every_item_of_every_meal():
    meals = [{"items": [{"kcal": 200.5, "protein_g": 6, "carbs_g": 30, "fat_g": 5}, {"kcal": 100, "protein_g": 4, "carbs_g": 10, "fat_g": 2}]},
             {"items": [{"kcal": 50, "protein_g": 1, "carbs_g": 12, "fat_g": 0}]}]
    assert totals_of(meals) == {"kcal": 350.5, "protein_g": 11, "carbs_g": 52, "fat_g": 7}


def test_progress_pairs_each_macro_with_its_own_target_and_rounds_for_display():
    out = progress_for({"kcal": 900.04, "protein_g": 30, "carbs_g": 100, "fat_g": 20}, (1800, 120, 200, 40))
    assert (out.kcal.eaten, out.kcal.target, out.kcal.percent) == (900.0, 1800, 50)
    assert progress_for({"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}, (1407.6, 116.4, 148.2, 38.7)).kcal.target == 1408   # whole numbers, like the Targets screen
    assert (out.protein_g.percent, out.carbs_g.percent, out.fat_g.percent) == (25, 50, 50)
    assert progress_for({"kcal": 3600, "protein_g": 0, "carbs_g": 0, "fat_g": 0}, (1800, 120, 200, 40)).kcal.percent == 200    # over target shows over 100
