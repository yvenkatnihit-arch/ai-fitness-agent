"""Step 7.10b (D-089): cuisine-neutral dish categories land in the right meal roles, are portioned in bowls and cups, and a whole week can be
built from them. The foods below are SYNTHETIC test data (invented, plausible numbers), not real nutrition data."""

import pytest

from app.calc.meal_plan_payload import HOUSEHOLD_UNITS, build_payload, verify_payload
from app.calc.meal_pool import PoolFood, build_pool
from app.calc.meal_portions import HALF_UNITS, describe, portion_spec
from app.calc.meal_solver import DayTargets
from app.llm.client import LLMBusy
from app.workflows.pick_meals import PoolTooSmall, pick_meals
from datetime import date
from fooddata import checks, units as u

TARGETS = DayTargets(1800, 80, 225, 56, 1728, 1872, 92)
_ids = iter(range(50_000, 60_000))


def food(key, category, diet, kcal, p, c, f, units=(), cuisines=("mediterranean",)):
    return PoolFood(next(_ids), key, key.replace("_", " ").title(), category, diet, float(kcal), float(p), float(c), float(f), "ready",
                    (), tuple(units), tuple(cuisines))


def synthetic_mediterranean() -> list[PoolFood]:
    return [
        food("couscous", "dish_grain", "vegan", 112, 3.8, 23, 0.2, [("cup", 157.0)]), food("bulgur_pilaf", "dish_grain", "vegan", 120, 3.5, 21, 2.5, [("cup", 150.0)]),
        food("rice_pilaf", "dish_grain", "vegan", 150, 3, 27, 3, [("cup", 160.0)]), food("pita", "dish_bread", "vegan", 275, 9, 55, 1.2, [("piece", 60.0)]),
        food("lentil_soup", "dish_legume", "vegan", 85, 5.5, 13, 1.5, [("bowl", 300.0)]), food("chickpea_stew", "dish_legume", "vegan", 125, 6, 16, 4, [("bowl", 290.0)]),
        food("bean_stew", "dish_legume", "vegan", 110, 6.5, 15, 2.5, [("bowl", 290.0)]), food("falafel", "dish_legume", "vegan", 333, 13, 32, 18, [("piece", 17.0)]),
        food("hummus_bowl", "dish_legume", "vegan", 180, 8, 18, 8, [("cup", 245.0)]),
        food("grilled_chicken", "dish_meat_fish", "non_vegetarian", 165, 28, 0, 5, [("piece", 70.0)]),
        food("baked_fish", "dish_meat_fish", "non_vegetarian", 130, 22, 1, 4, [("piece", 90.0)]), food("kebab", "dish_meat_fish", "non_vegetarian", 220, 20, 3, 14, [("piece", 45.0)]),
        food("tabbouleh", "dish_vegetable", "vegan", 90, 2.5, 10, 4.5, [("bowl", 150.0)]), food("greek_salad", "dish_vegetable", "vegetarian", 110, 3.5, 6, 8, [("bowl", 200.0)]),
        food("roasted_veg", "dish_vegetable", "vegan", 95, 2, 12, 4.5, [("cup", 150.0)]), food("eggplant_stew", "dish_vegetable", "vegan", 100, 2, 11, 6, [("bowl", 220.0)]),
        food("hummus", "dish_dip", "vegan", 240, 8, 14, 17, [("tbsp", 15.0)]), food("tzatziki", "dish_dip", "vegetarian", 75, 4, 4, 5), food("baba_ganoush", "dish_dip", "vegan", 130, 3, 9, 10),
        food("shakshuka", "dish_breakfast", "eggetarian", 120, 7, 7, 7, [("piece", 160.0)]), food("ful_medames", "dish_breakfast", "vegan", 130, 7, 18, 3, [("bowl", 250.0)]),
        food("labneh_toast", "dish_breakfast", "vegetarian", 230, 9, 28, 9, [("piece", 90.0)]), food("oats_bowl", "dish_breakfast", "vegetarian", 150, 6, 22, 4, [("bowl", 250.0)]),
        food("orange", "fruit", "vegan", 47, 0.9, 11, 0.1, [("piece", 130.0)]), food("grapes", "fruit", "vegan", 69, 0.7, 17, 0.2, [("cup", 150.0)]),
        food("almonds", "nut_seed", "vegan", 579, 21, 22, 50), food("walnuts", "nut_seed", "vegan", 654, 15, 14, 65),
    ]


def down(prompt):
    raise LLMBusy()


# ---------- roles ----------

def keys(pool, slot, role):
    return {f.key for f in pool[slot].roles[role]}


def test_each_neutral_category_lands_in_the_right_role():
    pool = build_pool(synthetic_mediterranean(), "non_vegetarian", cuisines=["mediterranean"])
    assert {"couscous", "bulgur_pilaf", "rice_pilaf", "pita"} <= keys(pool, "lunch", "staple")
    assert {"lentil_soup", "falafel", "hummus_bowl", "grilled_chicken", "baked_fish", "kebab"} <= keys(pool, "lunch", "protein")
    assert {"tabbouleh", "greek_salad", "roasted_veg", "eggplant_stew"} == keys(pool, "lunch", "vegetable")
    assert {"hummus", "tzatziki", "baba_ganoush"} == keys(pool, "lunch", "side")
    assert {"shakshuka", "ful_medames", "labneh_toast", "oats_bowl", "pita"} <= keys(pool, "breakfast", "main")


def test_the_diet_still_decides_what_a_neutral_dish_may_be():
    pool = build_pool(synthetic_mediterranean(), "vegan", cuisines=["mediterranean"])
    assert "grilled_chicken" not in keys(pool, "lunch", "protein") and "greek_salad" not in keys(pool, "lunch", "vegetable")
    assert "hummus_bowl" in keys(pool, "dinner", "protein") and "tzatziki" not in keys(pool, "lunch", "side")


def test_a_pool_of_neutral_foods_has_no_missing_required_role_for_any_diet():
    for diet in ("vegan", "vegetarian", "eggetarian", "non_vegetarian"):
        pool = build_pool(synthetic_mediterranean(), diet, cuisines=["mediterranean"])
        assert all(not p.missing for p in pool.values()), (diet, [(s, p.missing) for s, p in pool.items() if p.missing])


# ---------- portions ----------

def spec(unit_list, category="dish_legume", key="x"):
    return portion_spec(PoolFood(1, key, "X", category, "vegan", 100, 5, 10, 2, "ready", (), tuple(unit_list)))


def test_a_bowl_and_a_cup_are_counted_in_halves_like_a_katori():
    for unit, grams in (("bowl", 300.0), ("cup", 240.0), ("katori", 150.0)):
        s = spec([(unit, grams)], "dish_legume")
        assert (s.unit, s.unit_g, s.step_g, s.steps_per_unit) == (unit, grams, grams / 2, 2)
        assert (s.min_steps, s.max_steps) == (1, 4)
    assert describe(spec([("bowl", 300.0)]), 3).text == "1.5 bowl (450 g)"


def test_katori_wins_over_bowl_and_bowl_over_cup_when_a_food_has_several():
    assert HALF_UNITS == ("katori", "bowl", "cup")
    assert spec([("cup", 240.0), ("bowl", 300.0), ("katori", 150.0)]).unit == "katori"
    assert spec([("cup", 240.0), ("bowl", 300.0)]).unit == "bowl"


def test_a_count_food_is_still_counted_in_pieces_and_a_piece_only_dish_too():
    assert spec([("piece", 60.0), ("cup", 240.0)], "dish_bread").unit == "piece"        # bread is piece-first
    assert spec([("piece", 17.0)], "dish_legume").unit == "piece"                        # falafel at 17 g is big enough to count in pieces (15 g and up)
    assert spec([("piece", 10.0)], "dish_legume").unit is None                           # ...an olive-sized 10 g piece is not a meal unit: grams


def test_the_new_bounds_exist_for_every_neutral_category():
    from app.calc.meal_portions import HALF_UNIT_BOUNDS
    assert {"dish_grain", "dish_legume", "dish_meat_fish", "dish_vegetable", "dish_dip"} <= set(HALF_UNIT_BOUNDS)
    assert HALF_UNIT_BOUNDS["dish_grain"] == (1, 6)


def test_a_dip_is_measured_in_grams_by_the_spoonful_not_by_the_bowl():
    assert spec([("tbsp", 15.0)], "dish_dip").unit is None                              # a spoon unit is not a meal step: the dip is weighed
    g = spec([("tbsp", 15.0)], "dish_dip")
    assert (g.unit, g.step_g, g.min_steps, g.max_steps) == (None, 10.0, 3, 12)          # 30 g to 120 g in 10 g steps


# ---------- a whole week ----------

@pytest.mark.parametrize("diet", ["vegan", "vegetarian", "eggetarian", "non_vegetarian"])
def test_a_week_can_be_built_and_verified_from_neutral_foods_alone(diet):
    foods = synthetic_mediterranean()
    week = pick_meals(foods, diet, [], TARGETS, "general_fitness", None, ask=down, cuisines=["mediterranean"])
    payload = build_payload(week, TARGETS, diet_type=diet, goal="general_fitness", week_start=date(2026, 11, 9), numbers_hidden=False)
    assert [d["day_of_week"] for d in payload["days"]] == list(range(1, 8))
    problems = verify_payload(payload, {f.key: f for f in foods}, diet_type=diet, dislikes=[], targets=TARGETS, cuisines=["mediterranean"])
    assert problems == []
    items = [i for d in payload["days"] for i in d["items"]]
    assert all(i["unit"] in (None, *HOUSEHOLD_UNITS) for i in items)
    assert "katori" not in {i["unit"] for i in items}                                    # nothing Indian shows up in a Mediterranean plan
    assert {"bowl", "cup", "piece"} & {i["unit"] for i in items}                         # the new household units are really used


def test_the_same_foods_are_refused_for_a_user_who_only_chose_indian():
    with pytest.raises(PoolTooSmall):
        pick_meals(synthetic_mediterranean(), "vegetarian", [], TARGETS, "general_fitness", None, ask=down, cuisines=["indian"])


# ---------- the data tooling ----------

def test_bowl_and_cup_volumes_are_defined_and_are_database_units():
    assert u.VOLUME_ML["bowl"] == 300 and u.VOLUME_ML["cup"] == 240 and {"bowl", "cup"} <= u.DB_UNITS


def test_a_bowl_is_volume_times_a_measured_density():
    foods = {"lentil_soup": ("usda_sr_legacy", "172921")}
    portions = {"172921": [("1 cup (8 fl oz)", 241.0)]}
    row = dict(key="lentil_soup", unit="bowl", method="volume", ref="172921", ref_portion="1 cup", ref_grams="241", note="")
    unit = u.check_unit(row, foods, portions, set())
    assert unit.grams == pytest.approx(300 * 241 / 236.6, abs=0.1)                       # 305.6 g
    assert "bowl 300 ml" in unit.source
    cup = u.check_unit({**row, "unit": "cup"}, foods, portions, set())
    assert cup.grams == pytest.approx(240 * 241 / 236.6, abs=0.1)


def test_a_volume_unit_cannot_be_copied_straight_from_a_usda_portion():
    foods = {"lentil_soup": ("usda_sr_legacy", "172921")}
    portions = {"172921": [("1 cup (8 fl oz)", 241.0)]}
    row = dict(key="lentil_soup", unit="cup", method="usda", ref="self", ref_portion="1 cup", ref_grams="241", note="")
    with pytest.raises(ValueError, match="volume unit"):
        u.check_unit(row, foods, portions, set())


@pytest.mark.parametrize("category, ok, too_low, too_high", [
    ("dish_grain", 110, 20, 600), ("dish_legume", 85, 5, 700), ("dish_meat_fish", 165, 30, 700),
    ("dish_vegetable", 60, 2, 500), ("dish_dip", 240, 10, 900),
])
def test_the_validator_knows_a_plausible_energy_range_for_each_neutral_category(category, ok, too_low, too_high):
    assert checks.check_dish_plausibility(category, ok) == []
    assert checks.check_dish_plausibility(category, too_low) and checks.check_dish_plausibility(category, too_high)
