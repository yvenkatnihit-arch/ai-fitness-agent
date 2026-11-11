"""Step 8.3 (D-107): ranking foods for "which foods are high in protein", offline. The ordering is code, never the model."""

import pytest

from app.agents.food_tools import FIND_FOODS, FindFoodsArgs
from app.agents.nutrition import NUTRITION_SPEC, nutrition_registry
from app.calc.food_rank import MAX_RESULTS, rank_foods, ranking_pool
from app.calc.meal_pool import PoolFood


def food(key, kcal, protein, diet="vegan", category="pulse", cuisines=("indian",), name=None, synonyms=()):
    return PoolFood(id=1, key=key, name=name or key.replace("_", " ").title(), category=category, diet_class=diet, kcal=kcal, protein_g=protein,
                    carbs_g=10, fat_g=2, review_status="ready", synonyms=synonyms, cuisines=cuisines)


FOODS = [food("tofu", 76, 8.1, category="dish_protein"), food("chicken_breast", 165, 31, "non_vegetarian", "meat"), food("paneer", 265, 18.3, "vegetarian", "dairy"),
         food("lentils", 116, 9, category="dish_dal"), food("cucumber", 15, 0.7, category="vegetable"), food("ghee", 900, 0, "vegetarian", "fat_oil"),
         food("egg", 143, 12.6, "eggetarian", "egg"), food("hummus", 166, 8, cuisines=("mediterranean",), category="dish_dip"),
         food("garam_masala", 300, 10, category="spice")]


def keys(foods):
    return [f.key for f in foods]


POOL = ranking_pool(FOODS, "non_vegetarian")          # what the tool really ranks: no spice, no cooking fat


def test_most_protein_orders_by_protein_then_name():
    assert keys(rank_foods(POOL, "most_protein", limit=4)) == ["chicken_breast", "paneer", "egg", "lentils"]
    tied = [food("b_food", 100, 5), food("a_food", 100, 5)]
    assert keys(rank_foods(tied, "most_protein")) == ["a_food", "b_food"]                    # ties by name: stable


def test_least_calories_skips_zero_calorie_entries_and_orders_ascending():
    assert keys(rank_foods(POOL, "least_calories", limit=3)) == ["cucumber", "tofu", "lentils"]
    assert keys(rank_foods([food("zero", 0, 0), food("one", 1, 0)], "least_calories")) == ["one"]


def test_protein_per_calorie_ignores_near_zero_calorie_foods_so_a_rounding_error_cannot_win():
    water = food("flavoured_water", 2, 0.5)
    got = keys(rank_foods(POOL + [water], "most_protein_per_calorie", limit=3))
    assert "flavoured_water" not in got and got == ["chicken_breast", "tofu", "egg"]


def test_filters_apply_before_the_cut():
    assert keys(rank_foods(POOL, "most_protein", min_protein_g=10)) == ["chicken_breast", "paneer", "egg"]
    assert keys(rank_foods(POOL, "most_protein", max_kcal=120)) == ["lentils", "tofu", "cucumber"]
    assert keys(rank_foods(POOL, "most_protein", kind="dishes")) == ["lentils", "tofu", "hummus"]
    assert keys(rank_foods(POOL, "most_protein", kind="ingredients", limit=2)) == ["chicken_breast", "paneer"]


def test_snacks_are_fruit_nuts_dairy_eggs_and_snack_dishes_not_vegetables():
    pool = POOL + [food("apple", 52, 0.3, category="fruit"), food("almonds", 579, 21, category="nut_seed"), food("khakhra", 380, 12, category="dish_snack")]
    assert set(keys(rank_foods(pool, "least_calories", kind="snacks", limit=8))) == {"apple", "hummus", "egg", "paneer", "khakhra", "almonds"}
    assert keys(rank_foods(pool, "least_calories", kind="snacks", limit=2)) == ["apple", "egg"]          # not cucumber: that is a vegetable, not a snack


def test_the_limit_is_capped_and_never_below_one():
    many = [food(f"f{i}", 100, i) for i in range(30)]
    assert len(rank_foods(many, "most_protein", limit=99)) == MAX_RESULTS and len(rank_foods(many, "most_protein", limit=0)) == 1


# ---------- who may see which food ----------

def test_a_vegan_never_sees_dairy_egg_or_meat_and_a_non_vegetarian_sees_meat():
    assert {f.key for f in ranking_pool(FOODS, "vegan")} == {"tofu", "lentils", "cucumber", "hummus"}
    assert "chicken_breast" in {f.key for f in ranking_pool(FOODS, "non_vegetarian")}
    assert "chicken_breast" not in {f.key for f in ranking_pool(FOODS, "eggetarian")} and "egg" in {f.key for f in ranking_pool(FOODS, "eggetarian")}


def test_spices_sweeteners_and_cooking_fat_are_never_ranked():
    assert {"garam_masala", "ghee"}.isdisjoint({f.key for f in ranking_pool(FOODS, "non_vegetarian")})


def test_dislikes_and_cuisines_narrow_the_pool():
    assert "lentils" not in {f.key for f in ranking_pool(FOODS, "vegan", dislikes=["lentil"])}
    assert {f.key for f in ranking_pool(FOODS, "vegan", cuisines=["mediterranean"])} == {"hummus"}
    named = [food("masoor", 116, 9, name="Masoor dal", synonyms=("red lentils",))]
    assert ranking_pool(named, "vegan", dislikes=["red lentils"]) == []                        # local names count, like in meal plans


def test_an_unknown_diet_is_refused():
    with pytest.raises(ValueError):
        ranking_pool(FOODS, "carnivore")


# ---------- wiring ----------

def test_the_nutrition_specialist_gained_the_ranking_tool_and_is_still_read_only():
    registry = nutrition_registry()
    assert registry.names() == NUTRITION_SPEC.tools == {"search_foods", "portion_nutrition", "find_foods"}
    assert all(t.scope == "read" for t in registry.all())
    NUTRITION_SPEC.check(registry)
    prompt = NUTRITION_SPEC.system_prompt
    assert "find_foods" in prompt and "SAME order" in prompt and "never re-sort" in prompt


def test_the_ranking_arguments_are_validated_and_cannot_name_a_user():
    FindFoodsArgs(sort_by="most_protein", diet="vegan", limit=3)
    for bad in ({"sort_by": "tastiest"}, {"sort_by": "most_protein", "diet": "carnivore"}, {"sort_by": "most_protein", "limit": 50},
                {"sort_by": "most_protein", "user_id": "x"}, {"sort_by": "most_protein", "max_kcal": 5000}, {}):
        with pytest.raises(Exception):
            FindFoodsArgs(**bad)
    assert FIND_FOODS.scope == "read"
