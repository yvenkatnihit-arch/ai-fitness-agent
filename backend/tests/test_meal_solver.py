"""The portion solver: hand-checked cases, the safety limits, honest failure and random-input guarantees."""

import random

import pytest

from app.calc.engine import Targets
from app.calc.meal_pool import PoolFood
from app.calc.meal_portions import portion_spec
from app.calc.meal_solver import DayTargets, MealItem, day_targets, solve_day

TOL = 1.5   # kcal: per-item rounding to 0.1


def food(key, category, kcal, p, c, f, units=()):
    return PoolFood(id=1, key=key, name=key, category=category, diet_class="vegan", kcal=kcal, protein_g=p, carbs_g=c,
                    fat_g=f, review_status="ready", units=tuple(units))


RICE = food("rice", "dish_rice", 130, 2.5, 28, 0.3, [("katori", 150.0)])      # one step = 75 g = 97.5 kcal
DAL = food("dal", "dish_dal", 120, 8, 15, 3, [("katori", 150.0)])             # one step = 75 g = 90 kcal
LUNCH_ONLY = {"lunch": 1.0}


def items(*foods, slot="lunch"):
    return [MealItem(slot, "x", f) for f in foods]


def targets(kcal, protein, carbs, fat, band=0.04, protein_cap=1.15):
    return DayTargets(kcal, protein, carbs, fat, kcal * (1 - band), kcal * (1 + band), protein * protein_cap)


def engine_targets(kcal, tdee, protein=120.0, fat=60.0, carbs=200.0):
    return Targets(bmr_kcal=1500, tdee_kcal=tdee, goal_target_kcal=kcal, calorie_target_kcal=kcal, protein_g=protein,
                   fat_g=fat, carbs_g=carbs, reasons=(), doctor_note=False, focus_on_habits=False)


def test_the_solver_finds_the_known_combination_exactly():
    # 4 steps of rice (300 g) + 3 steps of dal (225 g):
    #   kcal 4x97.5 + 3x90 = 660, protein 4x1.875 + 3x6 = 25.5, carbs 4x21 + 3x11.25 = 117.75, fat 4x0.225 + 3x2.25 = 7.65
    result = solve_day(items(RICE, DAL), targets(660, 25.5, 117.75, 7.65), LUNCH_ONLY)
    assert result.status == "ok"
    assert [s.steps for s in result.items] == [4, 3]
    assert [s.portion.text for s in result.items] == ["2 katori (300 g)", "1.5 katori (225 g)"]
    assert result.totals.kcal == pytest.approx(660, abs=0.2) and result.totals.protein_g == pytest.approx(25.5, abs=0.2)
    assert all(v == pytest.approx(100, abs=1) for v in result.percent_of_target.values())
    assert result.issues == ()


def test_one_item_hits_the_target_exactly():
    plain = food("plain", "dish_other", 200, 10, 30, 5)           # no units: 10 g steps, 60-300 g
    result = solve_day(items(plain), targets(600, 30, 90, 15), LUNCH_ONLY)
    assert result.items[0].portion.grams == 300 and result.totals.kcal == pytest.approx(600)


def test_it_is_deterministic():
    t = targets(660, 25.5, 117.75, 7.65)
    assert solve_day(items(RICE, DAL), t, LUNCH_ONLY) == solve_day(items(RICE, DAL), t, LUNCH_ONLY)


def test_an_empty_day_is_an_error():
    with pytest.raises(ValueError):
        solve_day([], targets(2000, 100, 250, 60))


def test_calories_stay_in_the_band_and_protein_under_the_cap():
    t = targets(2000, 120, 250, 60)
    meals = [MealItem("breakfast", "main", RICE), MealItem("lunch", "protein", DAL), MealItem("lunch", "staple", RICE),
             MealItem("dinner", "protein", DAL), MealItem("dinner", "staple", RICE), MealItem("evening_snack", "snack", DAL)]
    r = solve_day(meals, t)
    if r.status != "infeasible":
        assert t.kcal_min - TOL <= r.totals.kcal <= t.kcal_max + TOL
        assert r.totals.protein_g <= t.protein_max_g + TOL


def test_too_light_a_target_is_infeasible_and_says_why():
    heavy = food("heavy", "dish_other", 900, 10, 50, 80)              # the smallest portion is 60 g = 540 kcal
    r = solve_day(items(heavy), targets(300, 10, 30, 3))
    assert r.status == "infeasible" and "smallest portions" in r.issues[0] and "lighter" in r.issues[0]
    assert r.items == ()


def test_steps_too_coarse_to_land_in_the_band_say_no_combination_fits():
    # 40 kcal per 10 g step: 480 and 520 kcal are the neighbours, but the band (minus its safety margin) is 481-519.
    coarse = food("coarse", "dish_other", 400, 10, 50, 20)
    r = solve_day(items(coarse), targets(500, 10, 30, 3), LUNCH_ONLY)
    assert r.status == "infeasible" and "no combination" in r.issues[0]


def test_too_big_a_target_is_infeasible_and_says_why():
    r = solve_day(items(RICE, DAL), targets(5000, 200, 600, 100))     # the largest portions give 945 kcal
    assert r.status == "infeasible" and "largest portions" in r.issues[0] and "more filling" in r.issues[0]


def test_low_protein_is_reported_not_hidden():
    carbs_only = food("sugar_rice", "dish_rice", 130, 0.5, 30, 0.1, [("katori", 150.0)])
    r = solve_day(items(carbs_only, carbs_only), targets(500, 60, 70, 15), LUNCH_ONLY)
    assert r.status == "issues" and any("protein" in i for i in r.issues)


def test_protein_never_exceeds_the_kidney_cap():
    protein_rich = food("paneer_bhurji", "dish_curry_meat", 250, 20, 5, 18, [("katori", 150.0)])
    cap = targets(1000, 40, 100, 30, protein_cap=1.0)               # the kidney case: cap == target
    r = solve_day(items(protein_rich, RICE, RICE, DAL), cap, LUNCH_ONLY)
    if r.status != "infeasible":
        assert r.totals.protein_g <= 40 + TOL


def test_when_the_protein_cap_is_the_reason_the_message_says_so():
    paneer = food("paneer", "dish_other", 300, 25, 5, 22)             # one 10 g step: 30 kcal and 2.5 g protein
    r = solve_day(items(paneer), targets(600, 20, 10, 40, protein_cap=1.0), LUNCH_ONLY)   # 20 steps = 50 g protein > 20 g cap
    assert r.status == "infeasible" and "protein cap" in r.issues[0] and "lower-protein" in r.issues[0]
    assert "50 g" in r.issues[0]


def test_meal_shares_are_followed_when_possible():
    meals = [MealItem("lunch", "staple", RICE), MealItem("lunch", "protein", DAL),
             MealItem("dinner", "staple", RICE), MealItem("dinner", "protein", DAL)]
    r = solve_day(meals, targets(900, 40, 150, 20), {"lunch": 0.5, "dinner": 0.5})
    assert r.status != "infeasible"
    assert abs(r.slot_kcal["lunch"] - r.slot_kcal["dinner"]) <= 100        # each meal about half the day


def test_the_hard_limits_hold_for_random_days():
    rng = random.Random(7)
    categories = ["dish_rice", "dish_dal", "dish_sabzi", "dish_bread", "dairy", "fruit", "nut_seed", "dish_other"]
    feasible = 0
    for trial in range(80):
        foods = []
        for k in range(rng.randint(3, 9)):
            cat = rng.choice(categories)
            units = rng.choice([[], [("katori", float(rng.choice([100, 150, 180])))], [("piece", float(rng.choice([30, 43, 60])))],
                                [("glass", 240.0)]])
            foods.append(food(f"f{trial}_{k}", cat, rng.uniform(40, 450), rng.uniform(0, 25), rng.uniform(0, 60), rng.uniform(0, 30), units))
        slot_names = ["breakfast", "lunch", "evening_snack", "dinner"]
        meals = [MealItem(rng.choice(slot_names), "x", f) for f in foods]
        kcal = rng.uniform(1300, 3200)
        t = targets(kcal, rng.uniform(60, 180), rng.uniform(120, 400), rng.uniform(30, 100), band=0.04, protein_cap=rng.choice([1.0, 1.15]))
        r = solve_day(meals, t)
        if r.status == "infeasible":
            assert r.issues and r.items == ()
            continue
        feasible += 1
        assert t.kcal_min - TOL <= r.totals.kcal <= t.kcal_max + TOL, (trial, r.totals.kcal, t.kcal_min, t.kcal_max)
        assert r.totals.protein_g <= t.protein_max_g + TOL, (trial, r.totals.protein_g, t.protein_max_g)
        for solved, meal in zip(r.items, meals):
            spec = portion_spec(meal.food)
            assert spec.min_steps <= solved.steps <= spec.max_steps
    assert feasible >= 20      # the property test is not vacuous


# --- the daily target and its hard band come from the engine's own clamps ---

def test_a_fat_loss_target_at_the_deficit_cap_cannot_be_undercut():
    # TDEE 2500, 25% deficit cap -> 1875 is the lowest safe target; 4% below would breach it, so the band starts AT the target.
    t = day_targets(engine_targets(1875, 2500), weight_kg=80, sex="male", flags=set())
    assert t.kcal_min == pytest.approx(1875) and t.kcal_max == pytest.approx(1875 * 1.04)


def test_a_gain_target_at_the_surplus_cap_cannot_be_exceeded():
    t = day_targets(engine_targets(2750, 2500), weight_kg=70, sex="male", flags=set())    # 10% surplus cap
    assert t.kcal_max == pytest.approx(2750) and t.kcal_min == pytest.approx(2750 * 0.96)


def test_the_calorie_floor_is_a_hard_minimum():
    t = day_targets(engine_targets(1200, 1500), weight_kg=50, sex="female", flags=set())
    assert t.kcal_min >= 1200
    r = solve_day(items(RICE, DAL, slot="lunch"), t, LUNCH_ONLY)
    if r.status != "infeasible":
        assert r.totals.kcal >= 1200


def test_a_health_flag_uses_the_milder_deficit_cap():
    t = day_targets(engine_targets(2250, 2500), weight_kg=80, sex="male", flags={"diabetes"})   # 10% cap -> 2250
    assert t.kcal_min == pytest.approx(2250)


def test_eating_disorder_history_gets_no_deficit_at_all():
    t = day_targets(engine_targets(2500, 2500), weight_kg=60, sex="female", flags={"eating_disorder_history"})
    assert t.kcal_min == pytest.approx(2500)


def test_protein_cap_is_the_target_for_kidney_and_a_little_headroom_otherwise():
    kidney = day_targets(engine_targets(2000, 2300, protein=60), weight_kg=75, sex="male", flags={"kidney"})
    normal = day_targets(engine_targets(2000, 2300, protein=120), weight_kg=75, sex="male", flags=set())
    assert kidney.protein_max_g == 60
    assert normal.protein_max_g == pytest.approx(138)                  # 120 x 1.15, below 35% of calories
    greedy = day_targets(engine_targets(1500, 1700, protein=120), weight_kg=75, sex="male", flags=set())
    assert greedy.protein_max_g <= 0.35 * greedy.kcal_max / 4 + 1e-9   # never above 35% of calories
