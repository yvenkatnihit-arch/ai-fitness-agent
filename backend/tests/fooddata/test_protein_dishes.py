"""Step 7.10d-3 (D-093): the high-protein dishes and ingredients in the real data files. Offline: reads data/*.csv, never the database."""

import csv

import pytest

from app.calc.meal_portions import portion_spec
from fooddata import build, recipes as recipe_data
from fooddata.checks import DISH_KCAL_RANGES
from tests.fooddata.test_mediterranean_data import pool_foods, units, validated

DISHES = {   # key: (diet class, category, cuisines, minimum grams of protein per 100 g)
    "tofu_bhurji": ("vegan", "dish_protein", "indian", 10), "paneer_bhurji": ("vegetarian", "dish_protein", "indian", 14),
    "paneer_tikka": ("vegetarian", "dish_protein", "indian", 15), "egg_bhurji": ("eggetarian", "dish_protein", "indian", 8),
    "egg_white_omelette": ("eggetarian", "dish_breakfast", "indian;mediterranean", 9), "moong_chilla": ("vegan", "dish_breakfast", "indian", 7),
    "besan_chilla": ("vegan", "dish_breakfast", "indian", 7), "protein_chilla": ("vegan", "dish_breakfast", "indian", 12),
    "sprouts_chaat": ("vegan", "dish_vegetable", "indian", 1.5), "chana_chaat": ("vegan", "dish_legume", "indian;mediterranean", 4.5),
    "chicken_tikka": ("non_vegetarian", "dish_curry_meat", "indian", 22), "greek_yogurt_fruit_bowl": ("vegetarian", "dish_breakfast", "indian;mediterranean", 6.5),
}


def test_every_dish_is_in_the_files_unsigned_and_in_review():
    rows, items = recipe_data.read_recipes()
    by_key = {r["key"]: r for r in rows}
    v = validated()
    for key in DISHES:
        assert by_key[key]["reviewed_by"].strip() == "", f"{key} was signed off: only Venkat does that, in the file"
        assert [i for i in items if i["recipe"] == key]
        assert v[key]["status"] == "review"


@pytest.mark.parametrize("key", sorted(DISHES))
def test_diet_category_cuisines_and_protein_density(key):
    diet, category, cuisines, min_protein = DISHES[key]
    r = validated()[key]
    assert (r["diet_class"], r["category"], r["cuisines"]) == (diet, category, cuisines)
    assert float(r["protein_g"]) >= min_protein, (key, r["protein_g"])
    low, high = DISH_KCAL_RANGES[category]
    assert low <= float(r["kcal"]) <= high


def test_the_protein_chilla_really_has_more_protein_than_the_plain_besan_chilla():
    v = validated()
    assert float(v["protein_chilla"]["protein_g"]) > 1.4 * float(v["besan_chilla"]["protein_g"])


def test_egg_white_is_very_high_in_protein_for_its_calories():
    r = validated()["egg_white"]
    assert float(r["protein_g"]) / float(r["kcal"]) > 0.19 and r["diet_class"] == "eggetarian" and r["cuisines"] == "indian;mediterranean"


def test_soya_chunks_are_a_recorded_gap_with_nothing_substituted():
    rows = {r["key"]: r for r in build.read_ingredients()}
    g = rows["soya_chunks"]
    assert g["match"] == "none" and g["source"] == "" and "GAP" in g["note"]
    assert "soya_chunks" not in validated() and "soya_chunks" not in {i["ingredient"] for i in recipe_data.read_recipes()[1]}
    assert rows["rohu"]["match"] == "none"                                                    # the older fish gap is still honest too


def test_the_ingredients_added_for_these_dishes_are_validated():
    v = validated()
    assert v["soy_flour"]["category"] == "pulse" and float(v["soy_flour"]["protein_g"]) > 45
    assert v["moong_sprouts"]["diet_class"] == "vegan"
    assert v["chickpeas_cooked"]["cuisines"] == "indian;mediterranean" and v["greek_yogurt_lowfat"]["cuisines"] == "indian;mediterranean"


def test_units_for_the_new_dishes():
    u = {k: dict(x) for k, x in units().items()}
    assert u["paneer_tikka"] == {"piece": 32.0} and u["chicken_tikka"] == {"piece": 50.0}
    assert u["moong_chilla"] == {"piece": 50.0} and u["besan_chilla"] == {"piece": 55.0} and u["protein_chilla"] == {"piece": 55.0}
    assert {"katori"} == set(u["tofu_bhurji"]) == set(u["paneer_bhurji"]) == set(u["egg_bhurji"])
    assert set(u["chana_chaat"]) == {"katori", "cup"}                                          # so a Mediterranean plan can say cup


@pytest.mark.parametrize("key, low, high", [("paneer_tikka", 96.0, 320.0), ("chicken_tikka", 100.0, 400.0)])
def test_tikka_is_served_in_realistic_piece_counts(key, low, high):
    f = next(f for f in pool_foods() if f.key == key)
    s = portion_spec(f, "protein")
    assert s.unit == "piece" and (s.min_steps * s.step_g, s.max_steps * s.step_g) == (low, high)


def test_the_new_category_has_portion_and_validation_rules():
    from app.calc.meal_portions import HALF_UNIT_BOUNDS
    assert HALF_UNIT_BOUNDS["dish_protein"] == (1, 4) and "dish_protein" in DISH_KCAL_RANGES


def test_the_loader_still_reads_everything_and_holds_back_only_mediterranean_only_foods():
    from fooddata import load
    loadable, waiting = load.split_by_enabled(load.read_validated())
    assert set(waiting) == {"mediterranean"}
    keys = {f.key for f in loadable}
    assert {"tofu_bhurji", "paneer_tikka", "chicken_tikka", "egg_white", "egg_white_omelette", "chana_chaat"} <= keys    # Indian-tagged: loadable
    assert "chickpeas_cooked" in keys and "greek_yogurt_lowfat" in keys                                                   # shared: loadable as Indian
