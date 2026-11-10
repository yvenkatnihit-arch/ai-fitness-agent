"""Step 7.10a (D-088): foods belong to cuisines, a user picks one or more, and the meal pool and the plan verifier respect that (pure Python)."""

from dataclasses import replace
from datetime import date

import pytest

from app.calc.meal_plan_payload import build_payload, verify_payload
from app.calc.meal_pool import PoolFood, allowed_foods, build_pool, localised
from app.calc.meal_solver import DayTargets
from app.llm.client import LLMBusy
from app.workflows.pick_meals import PoolTooSmall, pick_meals
from tests.meal_fixtures import make_foods
from tests.test_meal_pool import FOODS as POOL_FOODS
from tests.test_meal_pool import keys

TARGETS = DayTargets(1800, 80, 225, 56, 1728, 1872, 92)


def tagged(foods, **cuisines_by_key):
    """The same foods, with the given keys moved to other cuisines (a tuple), everything else left Indian."""
    return [replace(f, cuisines=tuple(cuisines_by_key.get(f.key, f.cuisines))) for f in foods]


def down(prompt):
    raise LLMBusy()


# ---------- the field ----------

def test_a_food_is_indian_unless_it_says_otherwise():
    assert all(f.cuisines == ("indian",) for f in POOL_FOODS)


# ---------- the pool ----------

def test_no_cuisine_filter_means_every_cuisine():
    foods = tagged(POOL_FOODS, toor_dal=("mediterranean",))
    assert {f.key for f in allowed_foods(foods, "vegan", [])} == {f.key for f in allowed_foods(foods, "vegan", [], None)}
    assert "toor_dal" in {f.key for f in allowed_foods(foods, "vegan", [], None)}


def test_a_food_from_another_cuisine_is_left_out():
    foods = tagged(POOL_FOODS, toor_dal=("mediterranean",))
    assert "toor_dal" not in {f.key for f in allowed_foods(foods, "vegan", [], ["indian"])}
    assert "toor_dal" in {f.key for f in allowed_foods(foods, "vegan", [], ["mediterranean"])}


def test_several_cuisines_give_the_union_and_a_shared_food_counts_for_either():
    foods = tagged(POOL_FOODS, toor_dal=("mediterranean",), rajma=("indian", "mediterranean"), banana=("mediterranean",))
    indian = {f.key for f in allowed_foods(foods, "vegan", [], ["indian"])}
    med = {f.key for f in allowed_foods(foods, "vegan", [], ["mediterranean"])}
    both = {f.key for f in allowed_foods(foods, "vegan", [], ["indian", "mediterranean"])}
    assert "rajma" in indian and "rajma" in med                       # a shared food is in both
    assert "toor_dal" not in indian and "banana" not in indian and {"toor_dal", "banana", "rajma"} <= med
    assert both == indian | med


def test_the_diet_dislikes_and_cuisine_filters_all_apply_together():
    foods = tagged(POOL_FOODS, kadhi=("mediterranean",), paneer=("mediterranean",))
    got = {f.key for f in allowed_foods(foods, "vegetarian", ["rajma"], ["mediterranean"])}
    assert got == {"kadhi", "paneer"}                                  # vegetarian, not rajma, and from the one cuisine we asked for


def test_the_role_lists_only_contain_foods_from_the_chosen_cuisines():
    foods = tagged(POOL_FOODS, toor_dal=("mediterranean",), roti=("mediterranean",))
    pool = build_pool(foods, "vegan", cuisines=["indian"])
    assert "toor_dal" not in keys(pool, "lunch", "protein") and "roti" not in keys(pool, "lunch", "staple")
    assert "rice" in keys(pool, "lunch", "staple")


def test_a_cuisine_with_no_foods_leaves_every_required_role_empty_and_says_so():
    pool = build_pool(POOL_FOODS, "vegan", cuisines=["mediterranean"])
    assert all(p.missing for p in pool.values() if p.required)


def test_an_unknown_cuisine_is_not_an_error_here_it_just_matches_nothing():
    assert allowed_foods(POOL_FOODS, "vegan", [], ["martian"]) == []


# ---------- the week builder ----------

def test_a_week_is_built_only_from_the_chosen_cuisines():
    foods = make_foods()
    week = pick_meals(foods, "vegetarian", [], TARGETS, "muscle_gain", None, ask=down, cuisines=["indian"])
    assert week.days and all(i.food_key for d in week.days for i in d.solution.items)


def test_asking_for_a_cuisine_we_have_no_foods_for_is_a_clear_refusal():
    with pytest.raises(PoolTooSmall):
        pick_meals(make_foods(), "vegetarian", [], TARGETS, "muscle_gain", None, ask=down, cuisines=["mediterranean"])


def test_the_week_builder_without_a_filter_behaves_as_before():
    a = pick_meals(make_foods(), "vegetarian", [], TARGETS, "muscle_gain", None, ask=down)
    b = pick_meals(make_foods(), "vegetarian", [], TARGETS, "muscle_gain", None, ask=down, cuisines=["indian"])
    assert [[i.food_key for i in d.solution.items] for d in a.days] == [[i.food_key for i in d.solution.items] for d in b.days]


# ---------- the plan verifier ----------

def test_the_verifier_refuses_a_food_outside_the_users_cuisines():
    foods = make_foods()
    by_key = {f.key: f for f in foods}
    week = pick_meals(foods, "vegetarian", [], TARGETS, "muscle_gain", None, ask=down)
    payload = build_payload(week, TARGETS, diet_type="vegetarian", goal="muscle_gain", week_start=date(2026, 11, 9), numbers_hidden=False)
    assert verify_payload(payload, by_key, diet_type="vegetarian", dislikes=[], targets=TARGETS, cuisines=["indian"]) == []
    assert verify_payload(payload, by_key, diet_type="vegetarian", dislikes=[], targets=TARGETS) == []          # no filter: as before
    moved = {k: replace(f, cuisines=("mediterranean",)) for k, f in by_key.items()}
    problems = verify_payload(payload, moved, diet_type="vegetarian", dislikes=[], targets=TARGETS, cuisines=["indian"])
    assert problems and all("is not from your chosen cuisines" in p for p in problems)


def test_a_plan_made_for_one_cuisine_is_refused_if_the_users_cuisines_change_before_approval():
    """The approval step re-verifies against the cuisines saved TODAY, so editing your cuisines in Settings cannot let an old plan through."""
    foods = make_foods()
    week = pick_meals(foods, "vegetarian", [], TARGETS, "muscle_gain", None, ask=down)
    payload = build_payload(week, TARGETS, diet_type="vegetarian", goal="muscle_gain", week_start=date(2026, 11, 9), numbers_hidden=False)
    by_key = {f.key: f for f in foods}
    assert verify_payload(payload, by_key, diet_type="vegetarian", dislikes=[], targets=TARGETS, cuisines=["indian"]) == []
    assert verify_payload(payload, by_key, diet_type="vegetarian", dislikes=[], targets=TARGETS, cuisines=["mediterranean"]) != []


# ---------- units follow the user's cuisines (Step 7.10d) ----------

def with_units(*units):
    return replace(POOL_FOODS[0], key="curd_like", cuisines=("indian", "mediterranean"), units=tuple(units))


def test_a_non_indian_user_sees_a_cup_instead_of_a_katori_when_the_food_has_both():
    f = with_units(("katori", 155.0), ("cup", 245.0))
    assert localised(f, ["mediterranean"]).units == (("cup", 245.0),)


@pytest.mark.parametrize("cuisines", [None, ["indian"], ["indian", "mediterranean"]])
def test_an_indian_user_and_an_unfiltered_pool_keep_the_katori(cuisines):
    f = with_units(("katori", 155.0), ("cup", 245.0))
    assert localised(f, cuisines) is f


def test_a_food_with_only_a_katori_keeps_it_rather_than_losing_every_household_unit():
    f = with_units(("katori", 155.0))
    assert localised(f, ["mediterranean"]).units == (("katori", 155.0),)
    g = with_units(("katori", 155.0), ("tbsp", 15.0))
    assert localised(g, ["mediterranean"]) is g                       # a spoon unit is no substitute for a measure of the whole dish


def test_bowl_also_replaces_katori_and_other_units_are_untouched():
    f = with_units(("katori", 150.0), ("bowl", 300.0), ("piece", 40.0))
    assert localised(f, ["mediterranean"]).units == (("bowl", 300.0), ("piece", 40.0))


def test_the_pool_a_mediterranean_user_gets_is_localised_and_the_indian_pool_is_not():
    foods = [replace(f, cuisines=("indian", "mediterranean"), units=(("katori", 150.0), ("cup", 240.0))) if f.key == "toor_dal" else f for f in POOL_FOODS]
    med = {f.key: f for f in allowed_foods(foods, "vegan", [], ["mediterranean"])}
    ind = {f.key: f for f in allowed_foods(foods, "vegan", [], ["indian"])}
    assert med["toor_dal"].units == (("cup", 240.0),) and ind["toor_dal"].units == (("katori", 150.0), ("cup", 240.0))
