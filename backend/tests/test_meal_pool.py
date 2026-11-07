"""The meal-planning food pool: diet types, dislikes, roles and honest reporting of thin choices (pure Python)."""

import pytest

from app.calc.meal_pool import (
    ALL_SLOTS, ALLOWED_DIET_CLASSES, BIG_DAY_CALORIE_SHARE, BIG_DAY_KCAL, MIN_OPTIONS_PER_ROLE, SLOT_CALORIE_SHARE, SLOT_ROLES,
    SLOTS, PoolFood, allowed_foods, build_pool, disliked, shares_for, slots_for,
)


def food(key, category, diet="vegan", name=None, status="ready", synonyms=()):
    return PoolFood(id=abs(hash(key)) % 10_000, key=key, name=name or key.replace("_", " ").title(), category=category,
                    diet_class=diet, kcal=100, protein_g=5, carbs_g=15, fat_g=2, review_status=status, synonyms=tuple(synonyms))


FOODS = [
    food("roti", "dish_bread"), food("rice", "dish_rice"), food("pulao", "dish_rice"), food("idli", "dish_breakfast"),
    food("dosa", "dish_breakfast"), food("upma", "dish_breakfast"),
    food("toor_dal", "dish_dal", name="Toor dal", synonyms=["arhar dal"]), food("rajma", "dish_dal"), food("kadhi", "dish_dal", "vegetarian"),
    food("chicken_curry", "dish_curry_meat", "non_vegetarian"),
    food("aloo_gobi", "dish_sabzi"), food("palak", "dish_sabzi", name="Palak sabzi"), food("bhindi", "dish_sabzi", name="Bhindi sabzi"),
    food("paneer", "dairy", "vegetarian"), food("curd", "dairy", "vegetarian"), food("milk_whole", "dairy", "vegetarian"),
    food("egg", "egg", "eggetarian"), food("boiled_egg", "dish_side", "eggetarian"), food("raita", "dish_side", "vegetarian"),
    food("boiled_potato", "dish_side"), food("chana_boiled", "dish_side"), food("grilled_chicken", "dish_side", "non_vegetarian"),
    food("banana", "fruit"), food("apple", "fruit"), food("almonds", "nut_seed"),
    food("gulab_jamun", "dish_sweet", "vegetarian"), food("samosa", "dish_snack", "vegetarian"), food("garam_masala", "spice"),
    food("ghee", "fat_oil", "vegetarian"), food("chicken_breast", "meat", "non_vegetarian"), food("prawns", "fish", "non_vegetarian"),
    food("spinach", "vegetable"), food("toor_dal_raw", "pulse"),
]


def keys(pool, slot, role):
    return [f.key for f in pool[slot].roles[role]]


def test_slots_roles_and_calorie_shares_are_consistent():
    assert ALL_SLOTS == tuple(SLOT_ROLES) and set(SLOTS) < set(ALL_SLOTS)
    assert SLOTS == tuple(SLOT_CALORIE_SHARE) and set(BIG_DAY_CALORIE_SHARE) == set(ALL_SLOTS)
    assert sum(SLOT_CALORIE_SHARE.values()) == pytest.approx(1.0) and sum(BIG_DAY_CALORIE_SHARE.values()) == pytest.approx(1.0)


def test_big_days_get_a_mid_morning_meal():
    assert slots_for(BIG_DAY_KCAL - 1) == SLOTS and slots_for(BIG_DAY_KCAL) == ALL_SLOTS and slots_for(3200) == ALL_SLOTS
    assert shares_for(SLOTS) == SLOT_CALORIE_SHARE and shares_for(ALL_SLOTS) == BIG_DAY_CALORIE_SHARE
    pool = build_pool(FOODS, "vegetarian", slots=ALL_SLOTS)
    assert list(pool) == list(ALL_SLOTS) and keys(pool, "mid_morning", "snack") == keys(pool, "evening_snack", "snack")
    assert list(build_pool(FOODS, "vegetarian")) == list(SLOTS)


@pytest.mark.parametrize("diet,forbidden", [
    ("vegan", {"paneer", "curd", "kadhi", "egg", "boiled_egg", "chicken_curry", "raita", "milk_whole"}),
    ("vegetarian", {"egg", "boiled_egg", "chicken_curry", "grilled_chicken"}),
    ("eggetarian", {"chicken_curry", "grilled_chicken"}),
])
def test_a_diet_never_sees_foods_it_cannot_eat(diet, forbidden):
    pool = build_pool(FOODS, diet)
    seen = {f.key for slot in pool.values() for foods in slot.roles.values() for f in foods}
    assert not (seen & forbidden), seen & forbidden


def test_non_vegetarians_get_everything_that_fits_a_role():
    pool = build_pool(FOODS, "non_vegetarian")
    assert "chicken_curry" in keys(pool, "lunch", "protein") and "grilled_chicken" in keys(pool, "dinner", "protein")


def test_unknown_diet_is_an_error_not_a_guess():
    with pytest.raises(ValueError):
        build_pool(FOODS, "keto")
    assert set(ALLOWED_DIET_CLASSES) == {"vegan", "vegetarian", "eggetarian", "non_vegetarian"}


def test_sweets_fried_snacks_spices_oils_and_raw_meat_or_fish_are_never_offered():
    allowed = {f.key for f in allowed_foods(FOODS, "non_vegetarian", [])}
    assert not allowed & {"gulab_jamun", "samosa", "garam_masala", "ghee", "chicken_breast", "prawns"}


def test_raw_ingredients_are_not_meals():
    pool = build_pool(FOODS, "vegan")
    seen = {f.key for slot in pool.values() for foods in slot.roles.values() for f in foods}
    assert "spinach" not in seen and "toor_dal_raw" not in seen            # only cooked dishes, fruit, dairy, nuts, eggs


def test_meals_are_built_from_roles():
    pool = build_pool(FOODS, "vegetarian")
    assert pool["lunch"].required == ("staple", "protein", "vegetable") == pool["dinner"].required
    assert keys(pool, "lunch", "staple") == ["pulao", "rice", "roti"]                         # sorted by name
    assert keys(pool, "lunch", "protein") == ["chana_boiled", "kadhi", "paneer", "rajma", "toor_dal"]
    assert keys(pool, "lunch", "side") == ["boiled_potato", "curd", "raita"]
    assert keys(pool, "breakfast", "main") == ["dosa", "idli", "roti", "upma"]
    assert keys(pool, "evening_snack", "snack") == ["almonds", "apple", "banana", "chana_boiled", "curd"]


def test_dislikes_match_names_and_local_names_case_insensitively():
    toor = next(f for f in FOODS if f.key == "toor_dal")
    assert disliked(toor, ["TOOR"]) and disliked(toor, ["arhar"]) and disliked(toor, [" dal "])
    assert not disliked(toor, ["karela"]) and not disliked(toor, ["", "  "])
    pool = build_pool(FOODS, "vegetarian", dislikes=["dal", "palak"])
    assert "toor_dal" not in keys(pool, "lunch", "protein") and "palak" not in keys(pool, "lunch", "vegetable")


def test_verified_foods_come_before_unverified_ones():
    foods = [food("zeta_dal", "dish_dal"), food("alpha_dal", "dish_dal", status="review"), food("beta_dal", "dish_dal")]
    assert keys(build_pool(foods, "vegan"), "lunch", "protein") == ["beta_dal", "zeta_dal", "alpha_dal"]


def test_thin_and_missing_roles_are_reported_not_hidden():
    pool = build_pool(FOODS, "vegan")
    assert "main" not in pool["breakfast"].thin                               # idli, dosa, upma, roti = 4 options
    assert "side" in pool["lunch"].thin                                       # only boiled potato: fewer than 3
    only_rice = build_pool([food("rice", "dish_rice")], "vegan")
    assert only_rice["lunch"].missing == ("protein", "vegetable") and "staple" in only_rice["lunch"].thin
    assert MIN_OPTIONS_PER_ROLE == 3


def test_pool_is_stable_regardless_of_input_order():
    assert build_pool(FOODS, "vegetarian") == build_pool(list(reversed(FOODS)), "vegetarian")
