"""Step 7.10d (D-091): the Mediterranean / Middle Eastern recipes in the real data files. Offline: reads data/*.csv, never the database."""

import csv

import pytest

from app.calc.meal_pool import PoolFood, build_pool
from app.calc.meal_portions import portion_spec
from fooddata import load, recipes as recipe_data
from fooddata.build import VALIDATED
from fooddata.checks import DISH_KCAL_RANGES
from fooddata.units import UNITS_VALIDATED

# Drafted by Claude, waiting for Venkat's sign-off. A key is only removed from this set when he fills `reviewed_by`.
BATCH_1 = {
    "shakshuka": "eggetarian", "ful_medames": "vegan", "menemen": "eggetarian", "yogurt_walnut_honey": "vegetarian", "oats_yogurt_figs": "vegetarian",
    "feta_spinach_omelette": "eggetarian", "couscous_cooked": "vegan", "bulgur_pilaf": "vegan", "rice_vermicelli_pilaf": "vegan",
    "quinoa_pilaf": "vegan", "orzo_tomato": "vegan", "mujaddara": "vegan", "lentil_soup": "vegan", "chickpea_stew": "vegan", "falafel": "vegan",
    "fasolada": "vegan", "white_bean_salad": "vegan", "lentil_salad": "vegetarian",
}
BATCH_2 = {
    "chicken_souvlaki": "non_vegetarian", "chicken_shawarma": "non_vegetarian", "lamb_kofta": "non_vegetarian", "baked_sea_bass_tomato": "non_vegetarian",
    "grilled_salmon_lemon": "non_vegetarian", "garlic_shrimp": "non_vegetarian", "chicken_apricot_tagine": "non_vegetarian", "tuna_white_bean_salad": "non_vegetarian",
    "tabbouleh": "vegan", "greek_salad": "vegetarian", "fattoush": "vegan", "roasted_vegetables": "vegan", "ratatouille": "vegan", "eggplant_stew": "vegan",
    "okra_tomato_stew": "vegan", "stuffed_vine_leaves": "vegan", "green_beans_olive_oil": "vegan", "hummus": "vegan", "baba_ganoush": "vegan",
    "tzatziki": "vegetarian", "labneh": "vegetarian", "muhammara": "vegan",
}
BATCH_CATEGORY = {**{k: "dish_meat_fish" for k in list(BATCH_2)[:8]}, **{k: "dish_vegetable" for k in list(BATCH_2)[8:17]}, **{k: "dish_dip" for k in list(BATCH_2)[17:]}}
ALL_BATCHES = {**BATCH_1, **BATCH_2}
CATEGORY = {"shakshuka": "dish_breakfast", "ful_medames": "dish_breakfast", "menemen": "dish_breakfast", "yogurt_walnut_honey": "dish_breakfast",
            "oats_yogurt_figs": "dish_breakfast", "feta_spinach_omelette": "dish_breakfast", "couscous_cooked": "dish_grain", "bulgur_pilaf": "dish_grain",
            "rice_vermicelli_pilaf": "dish_grain", "quinoa_pilaf": "dish_grain", "orzo_tomato": "dish_grain"}


def validated() -> dict[str, dict]:
    with VALIDATED.open(encoding="utf-8", newline="") as handle:
        return {r["key"]: r for r in csv.DictReader(handle)}


def units() -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    with UNITS_VALIDATED.open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            out.setdefault(r["key"], []).append((r["unit"], float(r["grams"])))
    return out


def pool_foods() -> list[PoolFood]:
    u = units()
    return [PoolFood(i, r["key"], r["name"], r["category"], r["diet_class"], float(r["kcal"]), float(r["protein_g"]), float(r["carbs_g"]), float(r["fat_g"]),
                     r["status"], (), tuple(u.get(r["key"], [])), tuple(r["cuisines"].split(";")))
            for i, r in enumerate(validated().values(), 1)]


# ---------- the recipes ----------

def test_every_batch_recipe_is_in_the_files_as_mediterranean_and_unsigned():
    rows, items = recipe_data.read_recipes()
    by_key = {r["key"]: r for r in rows}
    assert set(ALL_BATCHES) <= set(by_key)
    for key in ALL_BATCHES:
        assert by_key[key]["cuisines"] == "mediterranean"
        assert by_key[key]["reviewed_by"].strip() == "", f"{key} was signed off: only Venkat does that, in the file"
        assert [i for i in items if i["recipe"] == key], f"{key} has no ingredients"


def test_every_batch_recipe_made_it_into_the_validated_file_as_review_not_ready():
    v = validated()
    for key in ALL_BATCHES:
        assert v[key]["status"] == "review" and v[key]["cuisines"] == "mediterranean"      # unsigned recipes are never "ready"


@pytest.mark.parametrize("key, diet", sorted(ALL_BATCHES.items()))
def test_the_diet_class_is_computed_from_the_ingredients(key, diet):
    assert validated()[key]["diet_class"] == diet


@pytest.mark.parametrize("key", sorted(ALL_BATCHES))
def test_the_nutrition_is_plausible_and_internally_consistent(key):
    r = validated()[key]
    kcal, p, c, f, fib = float(r["kcal"]), float(r["protein_g"]), float(r["carbs_g"]), float(r["fat_g"]), float(r["fiber_g"] or 0)
    low, high = DISH_KCAL_RANGES[r["category"]]
    assert low <= kcal <= high
    atwater = 4 * p + 4 * c + 9 * f + 2 * fib                                            # energy rebuilt from the macros
    assert abs(atwater - kcal) / kcal < 0.25, (key, kcal, atwater)
    assert p + c + f + fib <= 100


def test_the_dishes_sit_in_the_categories_the_meal_roles_expect():
    v = validated()
    for key, category in CATEGORY.items():
        assert v[key]["category"] == category
    assert {v[k]["category"] for k in ("mujaddara", "lentil_soup", "chickpea_stew", "falafel", "fasolada", "white_bean_salad", "lentil_salad")} == {"dish_legume"}


# ---------- household units ----------

def test_dishes_use_bowls_cups_and_pieces_never_katori():
    u = units()
    grams_only = {"yogurt_walnut_honey", "feta_spinach_omelette", "baked_sea_bass_tomato", "garlic_shrimp", "hummus", "baba_ganoush", "tzatziki", "labneh", "muhammara"}
    for key in ALL_BATCHES:
        assert key in u or key in grams_only, f"{key} has no household unit (grams only)"
        assert "katori" not in {name for name, _ in u.get(key, [])}
    assert dict(u["falafel"]) == {"piece": 27.0}
    assert {name for name, _ in u["lentil_soup"]} == {"bowl"} and {name for name, _ in u["couscous_cooked"]} == {"cup"}


def test_a_bowl_of_soup_and_a_cup_of_couscous_weigh_what_the_usda_densities_say():
    u = {k: dict(v) for k, v in units().items()}
    assert u["lentil_soup"]["bowl"] == pytest.approx(300 * 241 / 236.6, abs=0.1)         # 305.6 g
    assert u["couscous_cooked"]["cup"] == pytest.approx(240 * 157 / 236.6, abs=0.1)      # 159.3 g


def test_pita_is_counted_in_pieces_from_the_measured_usda_portion():
    u = {k: dict(v) for k, v in units().items()}
    assert u["pita_white"] == {"piece": 60.0} and u["pita_whole_wheat"] == {"piece": 64.0}


def test_falafel_is_portioned_in_a_realistic_number_of_pieces():
    f = next(f for f in pool_foods() if f.key == "falafel")
    s = portion_spec(f, "protein")
    assert (s.unit, s.step_g, s.min_steps, s.max_steps) == ("piece", 27.0, 2, 10)         # 54 g to 270 g, never 1 to 3 pieces


# ---------- what the meal roles can already use ----------

def test_a_mediterranean_user_already_has_breakfasts_staples_and_proteins_from_the_real_data():
    pool = build_pool(pool_foods(), "eggetarian", cuisines=["mediterranean"])          # the validated file, before anything is loaded
    keys = lambda slot, role: {f.key for f in pool[slot].roles[role]}                   # noqa: E731
    assert {"shakshuka", "ful_medames", "menemen", "yogurt_walnut_honey", "feta_spinach_omelette", "pita_white"} <= keys("breakfast", "main")
    vegetarian = {f.key for f in build_pool(pool_foods(), "vegetarian", cuisines=["mediterranean"])["breakfast"].roles["main"]}
    assert "shakshuka" not in vegetarian and "menemen" not in vegetarian and "yogurt_walnut_honey" in vegetarian
    assert {"couscous_cooked", "bulgur_pilaf", "quinoa_pilaf", "orzo_tomato", "pita_white"} <= keys("lunch", "staple")
    assert {"mujaddara", "lentil_soup", "chickpea_stew", "falafel", "fasolada", "white_bean_salad", "lentil_salad"} <= keys("lunch", "protein")
    assert "shakshuka" not in {f.key for f in build_pool(pool_foods(), "vegan", cuisines=["mediterranean"])["breakfast"].roles["main"]}   # eggs: not vegan


def test_the_indian_pool_is_unchanged_by_the_new_dishes():
    pool = build_pool(pool_foods(), "vegetarian", cuisines=["indian"])
    protein = {f.key for f in pool["lunch"].roles["protein"]}
    assert not {"mujaddara", "falafel", "lentil_soup", "fasolada"} & protein                # no Mediterranean dish leaks into an Indian plan
    assert {"masoor_dal_cooked", "rajma_curry", "chole"} <= protein                          # the Indian ones are all still there
    assert not {f.key for f in pool["breakfast"].roles["main"]} & {"ful_medames", "pita_white", "yogurt_walnut_honey"}


def test_the_loader_can_read_the_whole_validated_file_and_holds_back_only_mediterranean_only_foods():
    loadable, waiting = load.split_by_enabled(load.read_validated())
    assert set(waiting) == {"mediterranean"} and {"falafel", "mujaddara", "lentil_soup"} <= set(waiting["mediterranean"])
    assert all(f.cuisines == ("indian",) for f in loadable)


# ---------- batch 2 ----------

def test_batch_2_dishes_sit_in_their_categories_and_have_the_expected_units():
    v, u = validated(), {k: dict(x) for k, x in units().items()}
    for key, category in BATCH_CATEGORY.items():
        assert v[key]["category"] == category, key
    assert u["lamb_kofta"] == {"piece": 45.0} and u["stuffed_vine_leaves"] == {"piece": 24.0} and u["chicken_souvlaki"] == {"piece": 80.0}
    assert u["greek_salad"]["cup"] == pytest.approx(240 * 180 / 236.6, abs=0.1) and u["ratatouille"]["bowl"] == pytest.approx(300 * 241 / 236.6, abs=0.1)


@pytest.mark.parametrize("key, unit_g, low, high", [("lamb_kofta", 45.0, 90.0, 360.0), ("stuffed_vine_leaves", 24.0, 72.0, 240.0),
                                                     ("chicken_souvlaki", 80.0, 80.0, 320.0), ("falafel", 27.0, 54.0, 270.0)])
def test_pieces_are_served_in_realistic_counts(key, unit_g, low, high):
    f = next(f for f in pool_foods() if f.key == key)
    s = portion_spec(f, "protein")
    assert s.unit == "piece" and s.step_g == unit_g and (s.min_steps * s.step_g, s.max_steps * s.step_g) == (low, high)


def test_no_dip_is_served_by_the_bowl_but_by_the_spoonful_in_grams():
    f = next(f for f in pool_foods() if f.key == "hummus")
    s = portion_spec(f, "side")
    assert s.unit is None and (s.min_steps * s.step_g, s.max_steps * s.step_g) == (30.0, 120.0)


@pytest.mark.parametrize("diet", ["vegan", "vegetarian", "eggetarian", "non_vegetarian"])
def test_a_whole_mediterranean_week_can_now_be_built_from_the_real_data_for_every_diet(diet):
    from datetime import date

    from app.calc.engine import calculate_targets
    from app.calc.meal_plan_payload import build_payload, verify_payload
    from app.calc.meal_solver import day_targets
    from app.calc.meal_week import emphasis_for
    from app.llm.client import LLMBusy
    from app.workflows.pick_meals import pick_meals
    from evals.meal_cases import FAT_LOSS_F

    def down(prompt):
        raise LLMBusy()
    foods = pool_foods()
    e = calculate_targets(FAT_LOSS_F)
    t = day_targets(e, weight_kg=FAT_LOSS_F.weight_kg, sex=FAT_LOSS_F.sex, flags=FAT_LOSS_F.screening_flags)
    week = pick_meals(foods, diet, [], t, FAT_LOSS_F.goal, emphasis_for(e.protein_g, e.calorie_target_kcal, FAT_LOSS_F.screening_flags),
                      ask=down, cuisines=["mediterranean"])
    payload = build_payload(week, t, diet_type=diet, goal=FAT_LOSS_F.goal, week_start=date(2026, 11, 9), numbers_hidden=False)
    assert verify_payload(payload, {f.key: f for f in foods}, diet_type=diet, dislikes=[], targets=t, cuisines=["mediterranean"]) == []
    items = [i for d in payload["days"] for i in d["items"]]
    assert "katori" not in {i["unit"] for i in items}                                    # nothing Indian shows up
    assert {"bowl", "cup", "piece"} & {i["unit"] for i in items}
    keys = [i["food_key"] for i in items]
    indian_only = {f.key for f in foods if f.cuisines == ("indian",)}
    assert not set(keys) & indian_only                                                    # not one Indian-only food in a Mediterranean plan
    assert len(set(keys)) >= 15                                                           # real variety, not the same few dishes all week
