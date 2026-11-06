import pytest

from fooddata import recipes as rc
from fooddata.recipes import Ingredient

# Per 100 g raw, values like our validated rows (carbs = available carbs, D-038)
RICE = Ingredient("rice_white", "vegan", kcal=365, protein_g=7.1, carbs_g=78.7, fat_g=0.7, fiber_g=1.3)
URAD = Ingredient("urad_dal", "vegan", kcal=298, protein_g=27.2, carbs_g=38.3, fat_g=1.4, fiber_g=None)
OIL = Ingredient("oil_sunflower", "vegan", kcal=884, protein_g=0, carbs_g=0, fat_g=100, fiber_g=0)
CURD = Ingredient("curd", "vegetarian", kcal=61, protein_g=3.5, carbs_g=4.7, fat_g=3.3, fiber_g=0)
EGG = Ingredient("egg", "eggetarian", kcal=143, protein_g=12.6, carbs_g=0.7, fat_g=9.5, fiber_g=0)
INGREDIENTS = {i.key: i for i in (RICE, URAD, OIL, CURD, EGG)}


def recipe(**changes) -> dict:
    base = dict(key="test_rice", name="Steamed rice", local_names="", category="dish_rice", cooked_g="300",
                reviewed_by="venkat", note="")
    return {**base, **changes}


def items(*pairs, recipe_key="test_rice") -> list[dict]:
    return [dict(recipe=recipe_key, ingredient=k, raw_g=str(g), note="") for k, g in pairs]


def test_one_ingredient_is_scaled_by_the_cooked_weight():
    # 100 g raw rice -> 300 g cooked: every nutrient per 100 g is a third of the raw value
    values = rc.per_100g_cooked([(RICE, 100)], cooked_g=300)
    assert values["kcal"] == pytest.approx(365 / 3, abs=0.01)
    assert values["carbs_g"] == pytest.approx(78.7 / 3, abs=0.01)
    assert values["fiber_g"] == pytest.approx(1.3 / 3, abs=0.01)


def test_ingredients_are_summed_by_weight():
    # 200 g rice + 10 g oil -> 500 g: kcal = (730 + 88.4) / 5
    values = rc.per_100g_cooked([(RICE, 200), (OIL, 10)], cooked_g=500)
    assert values["kcal"] == pytest.approx((2 * 365 + 0.1 * 884) / 5, abs=0.01)
    assert values["fat_g"] == pytest.approx((2 * 0.7 + 10) / 5, abs=0.01)


def test_fibre_is_unknown_when_too_much_of_the_weight_is_unmeasured():
    assert rc.per_100g_cooked([(RICE, 200), (URAD, 100)], 700)["fiber_g"] is None   # 33 % unmeasured
    assert rc.per_100g_cooked([(RICE, 200), (URAD, 5)], 500)["fiber_g"] is not None  # 2.4 %: small enough


def test_dish_diet_is_the_strictest_ingredient():
    assert rc.strictest_diet(["vegan", "vegan"]) == "vegan"
    assert rc.strictest_diet(["vegan", "vegetarian"]) == "vegetarian"
    assert rc.strictest_diet(["vegetarian", "eggetarian", "vegan"]) == "eggetarian"


def test_signed_off_clean_recipe_is_ready():
    result = rc.review_recipe(recipe(), items(("rice_white", 100)), INGREDIENTS)
    assert result.status == "ready"
    assert result.food.source == "computed" and result.row["diet_class"] == "vegan"
    assert "100 g rice_white -> 300 g cooked" in result.row["note"]


def test_recipe_waits_for_review_until_signed_off():
    assert rc.review_recipe(recipe(reviewed_by=""), items(("rice_white", 100)), INGREDIENTS).status == "review"


def test_diet_is_computed_from_ingredients_not_typed():
    result = rc.review_recipe(recipe(name="Curd rice"), items(("rice_white", 100), ("curd", 100)), INGREDIENTS)
    assert result.row["diet_class"] == "vegetarian"


def test_name_promising_dairy_without_dairy_is_blocked():
    # Name says paneer, but every ingredient is vegan: the recipe is wrong somewhere.
    result = rc.review_recipe(recipe(name="Paneer rice"), items(("rice_white", 100)), INGREDIENTS)
    assert result.status == "blocked" and any(i.check == "diet_class" for i in result.issues)


@pytest.mark.parametrize(
    "bad",
    [
        dict(items=items(("ragi", 100))),                     # a gap or unknown ingredient
        dict(items=items(("rice_white", 0))),                 # zero grams
        dict(items=items(("rice_white", "lots"))),            # not a number
        dict(items=[]),                                       # no ingredients
        dict(recipe=recipe(cooked_g="0")),                    # no cooked weight
    ],
)
def test_invalid_recipes_are_blocked(bad):
    result = rc.review_recipe(bad.get("recipe", recipe()), bad.get("items", items(("rice_white", 100))), INGREDIENTS)
    assert result.status == "blocked" and result.food is None


def test_odd_cooked_weight_is_flagged():
    # 100 g raw rice -> 1000 g "cooked" is 10x: probably a typo in cooked_g
    result = rc.review_recipe(recipe(cooked_g="1000"), items(("rice_white", 100)), INGREDIENTS)
    assert result.status == "review"
    assert {"yield", "dish_range"} <= {i.check for i in result.issues}


def test_items_for_a_missing_recipe_are_rejected():
    with pytest.raises(ValueError, match="don't exist"):
        rc.review_recipes([recipe()], items(("rice_white", 100), recipe_key="typo"), {})


def test_real_recipe_files_have_the_expected_columns():
    recipes, recipe_items = rc.read_recipes()
    assert recipes and recipe_items
    assert {i["recipe"] for i in recipe_items} <= {r["key"] for r in recipes}
