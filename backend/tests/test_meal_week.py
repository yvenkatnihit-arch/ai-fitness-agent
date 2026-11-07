"""Meal-week rules: validation, weekly repeat caps, tags, emphasis and the code fallback (pure Python)."""

import copy

import pytest

from app.calc.meal_pool import ALL_SLOTS, SLOTS, build_pool
from app.calc.meal_week import (
    UNIQUE_IN_DAY, allowed_keys, emphasis_for, fallback_day, food_tags, to_items, validate_day, validate_week, week_usage,
)
from tests.meal_fixtures import make_foods

FOODS = make_foods()
POOL = build_pool(FOODS, "vegetarian")
BY_KEY = {f.key: f for f in FOODS}


def good_day(i=0, pool=POOL, slots=SLOTS):
    return fallback_day(pool, slots, i)


def test_a_fallback_day_is_valid():
    for i in range(7):
        assert validate_day(good_day(i), POOL, SLOTS) == [], i


def test_fallback_is_deterministic_and_the_week_varies():
    assert good_day(2) == good_day(2)
    lunches = {good_day(i)["lunch"]["protein"] for i in range(7)}
    assert len(lunches) >= 4                                   # a week is not one repeated day
    assert good_day(0, ) != fallback_day(POOL, SLOTS, 0, offset=5)    # offsets give the search other rotations


def test_a_protein_or_vegetable_dish_is_never_repeated_within_a_day():
    for i in range(7):
        for offset in range(6):
            day = fallback_day(POOL, SLOTS, i, offset)
            used = [day[s][r] for s in SLOTS for r in day[s] if r in UNIQUE_IN_DAY and day[s][r]]
            assert len(used) == len(set(used)), (i, offset, used)


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: d.pop("lunch"), "missing meals: lunch"),
    (lambda d: d.update(brunch={}), "unknown meals: brunch"),
    (lambda d: d["lunch"].update(protein="made_up_dal"), "'made_up_dal' is not in the allowed list"),
    (lambda d: d["lunch"].update(protein="rice_0"), "'rice_0' is not in the allowed list"),            # real food, wrong role
    (lambda d: d["lunch"].update(protein=None), "lunch needs a protein dish"),
    (lambda d: d["dinner"].update(vegetable=""), "dinner needs a vegetable dish"),
    (lambda d: d["lunch"].update(snack="almonds"), "lunch has no role 'snack'"),
    (lambda d: d["lunch"].update(staple=42), "is not in the allowed list"),
    (lambda d: d["dinner"].update(protein=d["lunch"]["protein"]), "is used more than once in the day"),
    (lambda d: d["breakfast"].update(main="dal_0"), "'dal_0' is not in the allowed list"),
])
def test_bad_days_are_named(mutate, fragment):
    day = copy.deepcopy(good_day())
    mutate(day)
    assert any(fragment in p for p in validate_day(day, POOL, SLOTS)), validate_day(day, POOL, SLOTS)


def test_optional_roles_may_be_empty():
    day = copy.deepcopy(good_day())
    day["lunch"]["side"] = None
    day["breakfast"]["extra"] = None
    del day["dinner"]["side"]
    assert validate_day(day, POOL, SLOTS) == []


@pytest.mark.parametrize("junk", [None, [], "day", 5])
def test_junk_is_not_a_day(junk):
    assert validate_day(junk, POOL, SLOTS)


def test_a_dish_cannot_be_used_every_day():
    days = [copy.deepcopy(good_day(i)) for i in range(7)]
    for d in days:
        d["breakfast"]["main"] = "brk_0"               # the same breakfast all week
    problems = validate_week(days, POOL, SLOTS)
    assert set(problems) == {2, 3, 4, 5, 6}            # the cap is 2 (8 options for 7 breakfasts), so days 3 to 7 are refused
    assert all("used too often this week (at most 2 times)" in p[0] for p in problems.values())


def test_thin_pools_get_a_higher_repeat_cap():
    thin_foods = [f for f in FOODS if not (f.category == "dish_dal" and f.key not in ("dal_0", "dal_1", "dal_2"))]
    pool = build_pool(thin_foods, "vegetarian")
    days = []
    for i in range(7):                                                  # built one day at a time, aware of the week so far
        days.append(fallback_day(pool, SLOTS, i, 0, None, week_usage(days)))
    assert validate_week(days, pool, SLOTS) == {}                       # the least-used dish wins, so few dishes still spread out


def test_a_good_week_validates():
    assert validate_week([good_day(i) for i in range(7)], POOL, SLOTS) == {}


def test_to_items_matches_the_picks():
    day = good_day(1)
    items = to_items(day, POOL, SLOTS)
    assert {(i.slot, i.role): i.food.key for i in items} == {(s, r): k for s in SLOTS for r, k in day[s].items() if k}


def test_big_days_include_the_mid_morning_meal():
    pool = build_pool(FOODS, "vegetarian", slots=ALL_SLOTS)
    day = fallback_day(pool, ALL_SLOTS, 0)
    assert "mid_morning" in day and validate_day(day, pool, ALL_SLOTS) == []
    assert any("missing meals: mid_morning" in p for p in validate_day(good_day(), pool, ALL_SLOTS))


def test_tags_are_plain_words_computed_by_code():
    assert "protein-rich" in food_tags(BY_KEY["egg"]) and "protein-rich" not in food_tags(BY_KEY["rice_0"])
    assert "light" in food_tags(BY_KEY["chaas"]) and "calorie-dense" in food_tags(BY_KEY["almonds"])
    assert food_tags(BY_KEY["sabzi_0"]) == ("light",)                                    # 80 kcal per 100 g


@pytest.mark.parametrize("protein,kcal,flags,expected", [
    (150, 2000, set(), "high_protein"),      # 30% of calories
    (100, 2000, set(), None),                # 20%
    (150, 2000, {"kidney"}, "low_protein"),  # the kidney flag always wins
    (60, 2000, {"diabetes"}, None),
])
def test_emphasis_is_decided_by_code(protein, kcal, flags, expected):
    assert emphasis_for(protein, kcal, flags) == expected


def test_emphasis_steers_the_fallback_towards_the_right_dishes():
    density = lambda key: BY_KEY[key].protein_g / BY_KEY[key].kcal
    high = [fallback_day(POOL, SLOTS, i, 0, "high_protein")["lunch"]["protein"] for i in range(7)]
    low = [fallback_day(POOL, SLOTS, i, 0, "low_protein")["lunch"]["protein"] for i in range(7)]
    plain = [fallback_day(POOL, SLOTS, i, 0, None)["lunch"]["protein"] for i in range(7)]
    mean = lambda keys: sum(density(k) for k in keys) / len(keys)
    assert mean(high) > mean(low)


def test_allowed_keys_lists_the_pool_for_a_role():
    assert allowed_keys(POOL, "lunch", "protein") == [f.key for f in POOL["lunch"].roles["protein"]]
    assert allowed_keys(POOL, "lunch", "nope") == []
