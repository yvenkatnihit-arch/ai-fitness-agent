import pytest

from fooddata import checks as c
from fooddata.records import FoodRecord


def food(**changes) -> FoodRecord:
    base = dict(source="usda_sr_legacy", source_id="1", name="Lentils, raw", category="Legumes and Legume Products",
                kcal=352, protein_g=24.6, carbs_g=63.4, fat_g=1.1, fiber_g=10.7, carb_basis="by_difference")
    return FoodRecord(**{**base, **changes})


def checks_failed(issues):
    return {(i.check, i.severity) for i in issues}


def test_real_usda_lentils_pass_everything():
    # USDA SR Legacy lentils, raw: 352 kcal, 24.6 g protein, 63.4 g carbs (by difference), 1.1 g fat
    assert c.check_food(food()) == []


def test_real_cofid_style_food_passes_with_its_own_energy_formula():
    # CoFID-style: available carbs at 3.75 kcal/g. 4*7.4 + 3.75*16.4 + 9*1.4 = 103.7 -> stated 104
    cooked_dhal = food(source="uk_cofid", kcal=104, protein_g=7.4, carbs_g=16.4, fat_g=1.4, fiber_g=3.9,
                       carb_basis="available")
    assert c.check_food(cooked_dhal) == []


def test_missing_values_are_errors_not_zero():
    assert ("required", "error") in checks_failed(c.check_food(food(kcal=None)))
    assert ("required", "error") in checks_failed(c.check_food(food(fat_g=None)))


@pytest.mark.parametrize("change", [{"protein_g": -1}, {"kcal": 950}, {"carbs_g": 120}, {"fiber_g": -0.1}])
def test_impossible_values_are_errors(change):
    assert ("ranges", "error") in checks_failed(c.check_food(food(**change)))


def test_more_macros_than_fit_in_100g_is_an_error():
    issues = c.check_food(food(protein_g=60, carbs_g=40, fat_g=10, kcal=490))
    assert ("macro_mass", "error") in checks_failed(issues)


def test_fibre_counts_towards_mass_only_when_carbs_exclude_it():
    by_difference = food(protein_g=20, carbs_g=70, fat_g=10, fiber_g=20, kcal=450)
    available = food(protein_g=20, carbs_g=70, fat_g=10, fiber_g=20, kcal=440, carb_basis="available")
    assert ("macro_mass", "error") not in checks_failed(c.check_food(by_difference))
    assert ("macro_mass", "error") in checks_failed(c.check_food(available))


def test_energy_far_from_macros_is_flagged():
    # kJ typed into the kcal column is a classic unit error: 1473 "kcal" for lentils
    assert ("energy", "warning") in checks_failed(c.check_food(food(kcal=1473)))


def test_small_energy_gaps_are_fine():
    assert c.check_energy(food(kcal=330)) == []  # macros give ~362; a 9 % gap is within tolerance


def test_low_energy_foods_use_the_20_kcal_floor():
    lettuce = food(name="Lettuce", kcal=15, protein_g=1.4, carbs_g=2.9, fat_g=0.2, fiber_g=1.3)
    assert c.check_energy(lettuce) == []  # 15 vs 19: 21 % but only 4 kcal


def test_alcohol_counts_in_expected_energy():
    beer = food(name="Beer", kcal=43, protein_g=0.5, carbs_g=3.6, fat_g=0, alcohol_g=3.9)
    assert c.expected_kcal(beer) == pytest.approx(4 * 0.5 + 4 * 3.6 + 7 * 3.9)
    assert c.check_energy(beer) == []


@pytest.mark.parametrize(
    ("name", "category", "diet_class", "ok"),
    [
        ("Chicken, broilers, breast, raw", "Poultry Products", "non_vegetarian", True),
        ("Chicken, broilers, breast, raw", "Poultry Products", "vegetarian", False),
        ("Mackerel, raw", "Finfish and Shellfish Products", "eggetarian", False),
        ("Egg, whole, raw", "Dairy and Egg Products", "eggetarian", True),
        ("Egg, whole, raw", "Dairy and Egg Products", "vegetarian", False),
        ("Paneer", None, "vegetarian", True),
        ("Paneer", None, "vegan", False),
        ("Butter oil, anhydrous (ghee)", "Dairy and Egg Products", "vegan", False),
        ("Soy milk, unsweetened", "Legumes and Legume Products", "vegan", True),
        ("Peanut butter, smooth", "Legumes and Legume Products", "vegan", True),
        ("Eggplant, raw", "Vegetables and Vegetable Products", "vegan", True),
        ("Lentils, raw", "Legumes and Legume Products", "vegan", True),
        ("Bhaji, karela, with butter ghee, homemade", "DG", "vegan", False),
        # Real false alarms from the first build (Step 4.3b), now fixed:
        ("Yogurt, plain, whole milk", "Dairy and Egg Products", "vegetarian", True),   # "Egg" is only in the category
        ("Butter, Clarified butter (ghee)", "Dairy and Egg Products", "vegetarian", True),
        ("Nuts, coconut meat, raw", "Nut and Seed Products", "vegan", True),           # coconut flesh, not meat
        ("Tofu (firm) soya paneer", None, "vegan", True),                              # plant "paneer"
        ("Nuts, coconut milk, raw (liquid expressed from grated meat and water)", "Nut and Seed Products", "vegan", True),
        ("Ghee made from vegetable oil", None, "vegan", True),                         # vanaspati / dalda
        ("Vanaspati (vegetable ghee) dalda", None, "vegan", True),
        ("Ghee, butter", None, "vegan", False),                                        # real ghee is dairy
        ("Eggs, chicken, whole, boiled", None, "eggetarian", True),                    # a hen's egg (Step 4.3d)
        ("Eggs, chicken, whole, boiled", None, "vegetarian", False),                   # ...is still an egg
        # ...while the real problems are still caught:
        ("Curry, chicken and egg", None, "eggetarian", False),                         # real chicken + egg
        ("Egg, whole, raw, fresh", "Dairy and Egg Products", "vegetarian", False),    # egg in the NAME
        ("Yogurt, plain, whole milk", "Dairy and Egg Products", "vegan", False),       # dairy is never vegan
        ("Chicken thigh, raw", "Poultry Products", "eggetarian", False),
        ("Spiced cutlet", "Beef Products", "vegetarian", False),                       # category alone catches it
    ],
)
def test_diet_class_rules(name, category, diet_class, ok):
    assert (c.check_diet_class(name, category, diet_class) == []) is ok


@pytest.mark.parametrize(
    ("category", "kcal", "ok"),
    [
        ("dish_rice", 130, True),       # boiled rice
        ("dish_rice", 365, False),      # RAW rice mapped as a cooked dish
        ("dish_dal", 102, True),        # boiled red lentils
        ("dish_dal", 324, False),       # raw dal mapped as cooked dal
        ("dish_bread", 202, True),      # chapati without fat
        ("dish_bread", 90, False),
        ("pulse", 324, True),           # raw ingredients have no dish range
        ("dish_sweet", None, True),     # unknown energy is handled by check_required
    ],
)
def test_dish_plausibility(category, kcal, ok):
    assert (c.check_dish_plausibility(category, kcal) == []) is ok


def test_duplicates_are_found_within_a_source():
    foods = [food(source_id="1", name="Rice, white, raw"), food(source_id="2", name="Rice,  White,  raw"),
             food(source_id="3", name="Rice, brown, raw")]
    dupes = c.find_duplicates(foods)
    assert len(dupes) == 1 and len(next(iter(dupes.values()))) == 2


def test_sources_that_disagree_are_flagged():
    usda = food(kcal=352)
    assert c.compare_sources(usda, food(source="uk_cofid", kcal=330)) == []          # 6 % apart
    assert c.compare_sources(usda, food(source="uk_cofid", kcal=105))[0].check == "cross_source"  # cooked vs raw?
