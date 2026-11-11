"""Found by the accuracy audit (D-115): a pushup that was not found, a deadlift reported as missing instead of unsuitable, "fruits" that
included milk. Offline, real exercise library."""

from app.calc.exercise_filter import ExerciseNeeds, why_hidden
from app.calc.exercise_search import find_by_name, search
from app.calc.food_rank import GROUP_CATEGORIES, rank_foods
from tests.test_exercise_search import real_library
from tests.test_food_rank import food, keys


def test_a_name_written_without_the_hyphen_or_with_a_space_still_finds_the_exercise():
    lib = real_library()
    for query in ("pushup", "push up", "push-up", "pushups", "Push Ups"):
        names = [o.name for o in search(lib, query, limit=None)]
        assert "Push-Up" in names, query
    assert "Push" in find_by_name(lib, "pushup").name


def test_deadlift_is_in_the_library_and_is_correctly_unsuitable_for_a_home_beginner_not_missing():
    lib = real_library()
    found = search(lib, "deadlift", limit=None)
    assert found
    needs = ExerciseNeeds("home", "beginner", frozenset(), frozenset())
    assert all(why_hidden(o, needs) for o in found if "Barbell" in o.name)             # a barbell deadlift does not suit a home beginner


def test_a_food_group_kind_returns_only_that_group():
    pool = [food("apple", 52, 0.3, category="fruit"), food("papaya", 43, 0.5, category="fruit"), food("milk", 42, 3.4, "vegetarian", "dairy"),
            food("almonds", 579, 21, category="nut_seed"), food("lentils", 116, 9, category="pulse"), food("rice", 130, 2.7, category="cereal"),
            food("okra", 33, 1.9, category="vegetable")]
    assert set(GROUP_CATEGORIES) == {"fruits", "vegetables", "dairy", "nuts_seeds", "pulses", "grains", "beverages", "supplements", "desserts"}
    assert keys(rank_foods(pool, "least_calories", kind="fruits")) == ["papaya", "apple"]            # no milk in a fruit list
    assert keys(rank_foods(pool, "most_protein", kind="dairy")) == ["milk"] and keys(rank_foods(pool, "most_protein", kind="grains")) == ["rice"]
    assert keys(rank_foods(pool, "most_protein", kind="nuts_seeds")) == ["almonds"] and keys(rank_foods(pool, "most_protein", kind="vegetables")) == ["okra"]


def test_drinks_supplements_and_desserts_only_appear_when_asked_for_that_group():
    pool = [food("tea", 1, 0.0, category="beverage"), food("whey", 352, 78, "vegetarian", "supplement"), food("ice_cream", 207, 3.5, "vegetarian", "dessert"),
            food("lentils", 116, 9, category="pulse"), food("apple", 52, 0.3, category="fruit")]
    assert keys(rank_foods(pool, "least_calories")) == ["apple", "lentils"]                  # tea (1 kcal) does not top "low calorie foods"
    assert keys(rank_foods(pool, "most_protein")) == ["lentils", "apple"]                    # whey (78 g) does not top "high protein foods"
    assert keys(rank_foods(pool, "least_calories", kind="beverages")) == ["tea"]
    assert keys(rank_foods(pool, "most_protein", kind="supplements")) == ["whey"] and keys(rank_foods(pool, "most_protein", kind="desserts")) == ["ice_cream"]
    assert set(GROUP_CATEGORIES) >= {"beverages", "supplements", "desserts"}
