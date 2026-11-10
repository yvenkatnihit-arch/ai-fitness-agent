"""The portion solver on the REAL foods with REAL engine targets: the hard limits must hold for every diet and profile.

Dish choice here is naive on purpose (first allowed, or most protein per kcal): this tests the SOLVER's safety,
not plan quality (quality comes from the dish picker, step 6.7c).
"""

import pytest

from app.calc.engine import BodyProfile, calculate_targets
from app.calc.meal_pool import ALLOWED_DIET_CLASSES, SLOTS, build_pool
from app.calc.meal_portions import portion_spec
from app.calc.meal_solver import MealItem, day_targets, solve_day
from app.db import admin_transaction
from app.db.meal_foods import list_pool_foods

pytestmark = pytest.mark.db

INDIAN = ["indian"]   # these tests pin findings about the INDIAN pool; the other cuisines have their own tests (D-094)

TOL = 1.5
PROFILES = {
    "fatloss_f": BodyProfile(weight_kg=58, height_cm=162.5, age_years=31, sex="female", activity_level="light",
                             goal="fat_loss", screening_flags=frozenset(), pace="normal"),
    "muscle_m": BodyProfile(weight_kg=80, height_cm=178, age_years=27, sex="male", activity_level="moderate",
                            goal="muscle_gain", screening_flags=frozenset(), pace="normal"),
    "maintain_o": BodyProfile(weight_kg=70, height_cm=170, age_years=40, sex="other", activity_level="sedentary",
                              goal="general_fitness", screening_flags=frozenset(), pace="normal"),
    "flagged_f": BodyProfile(weight_kg=75, height_cm=165, age_years=45, sex="female", activity_level="light",
                             goal="fat_loss", screening_flags=frozenset({"diabetes"}), pace="fast"),
    "kidney_m": BodyProfile(weight_kg=82, height_cm=176, age_years=50, sex="male", activity_level="moderate",
                            goal="fat_loss", screening_flags=frozenset({"kidney"}), pace="normal"),
}


@pytest.fixture(scope="module")
def foods():
    with admin_transaction("test: read foods") as conn:
        return list_pool_foods(conn)


def build_items(foods, diet, pick):
    pool = build_pool(foods, diet, cuisines=INDIAN)

    def choose(choices):
        density = lambda f: f.protein_g / max(f.kcal, 1)
        if pick == "protein":
            return max(choices, key=density)
        return min(choices, key=density) if pick == "lowprotein" else choices[0]

    return [MealItem(slot, role, choose(c)) for slot in SLOTS for role, c in pool[slot].roles.items() if c]


@pytest.mark.parametrize("diet", list(ALLOWED_DIET_CLASSES))
@pytest.mark.parametrize("pick", ["first", "protein"])
@pytest.mark.parametrize("name", list(PROFILES))
def test_hard_limits_hold_on_real_foods(foods, diet, pick, name):
    profile = PROFILES[name]
    engine = calculate_targets(profile)
    t = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    items = build_items(foods, diet, pick)
    r = solve_day(items, t)
    assert r.status in ("ok", "issues", "infeasible")
    if r.status == "infeasible":
        assert r.issues and r.items == ()
        return
    assert t.kcal_min - TOL <= r.totals.kcal <= t.kcal_max + TOL
    assert r.totals.protein_g <= t.protein_max_g + TOL
    for solved, item in zip(r.items, items):
        spec = portion_spec(item.food, item.role)
        assert spec.min_steps <= solved.steps <= spec.max_steps
        assert 0 < solved.portion.grams <= 2000
    # the safety limits come from the engine: the day's calories never beat the calorie floor or the deficit caps
    assert r.totals.kcal >= {"female": 1200, "male": 1500, "other": 1500}[profile.sex] - TOL


def test_a_kidney_user_never_gets_more_protein_than_their_cap(foods):
    profile = PROFILES["kidney_m"]
    engine = calculate_targets(profile)
    t = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    assert t.protein_max_g == engine.protein_g                       # the cap IS the target (0.8 g/kg, D-023)
    for pick in ("first", "protein"):
        r = solve_day(build_items(foods, "non_vegetarian", pick), t)
        if r.status != "infeasible":
            assert r.totals.protein_g <= engine.protein_g + TOL, pick


def test_a_protein_packed_day_is_refused_for_a_kidney_user_instead_of_breaking_the_cap(foods):
    """Chicken and paneer in every role cannot reach the calorie floor under a ~66 g protein cap: the safe answer is 'no'."""
    profile = PROFILES["kidney_m"]
    engine = calculate_targets(profile)
    t = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    r = solve_day(build_items(foods, "non_vegetarian", "protein"), t)
    assert r.status == "infeasible" and r.items == ()
    assert "protein cap" in r.issues[0]                               # says WHY, so the picker can choose differently


def test_a_kidney_user_can_still_get_a_plan_from_ordinary_dishes(foods):
    profile = PROFILES["kidney_m"]
    engine = calculate_targets(profile)
    t = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    r = solve_day(build_items(foods, "vegetarian", "lowprotein"), t)
    assert r.status != "infeasible" and r.totals.protein_g <= engine.protein_g + TOL


def test_a_flagged_user_stays_inside_the_milder_deficit_cap(foods):
    profile = PROFILES["flagged_f"]
    engine = calculate_targets(profile)
    t = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    r = solve_day(build_items(foods, "vegetarian", "first"), t)
    if r.status != "infeasible":
        assert r.totals.kcal >= engine.tdee_kcal * 0.90 - TOL        # diabetes flag: at most a 10% deficit


@pytest.mark.parametrize("diet", ["vegetarian", "non_vegetarian"])
def test_a_3000_kcal_day_does_not_fit_the_bare_four_meal_skeleton(foods, diet):
    """The bare four-meal skeleton never makes a GOOD 3,000 kcal day (D-065). RESOLVED by step 6.7c, which adds a mid-morning meal and
    scales portions for big targets: see test_meal_week_real_foods.py::test_a_3000_kcal_day_now_fits_... Since the protein batch
    (D-093) added bigger dishes the bare skeleton is no longer outright infeasible, but it still cannot be an "ok" day."""
    profile = PROFILES["muscle_m"]
    engine = calculate_targets(profile)
    t = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    assert engine.calorie_target_kcal > 2800
    assert solve_day(build_items(foods, diet, "first"), t).status != "ok"


def test_a_typical_vegetarian_day_can_be_planned_well(foods):
    profile = PROFILES["maintain_o"]
    engine = calculate_targets(profile)
    t = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    r = solve_day(build_items(foods, "vegetarian", "protein"), t)
    # Calories and protein are what this checks. Picking the most protein-dense food in every role also picks very light items (a 36 kcal
    # snack), which leaves soft meal-split issues; those are not part of the claim and the week builder avoids them.
    assert 95 <= r.percent_of_target["kcal"] <= 105 and r.percent_of_target["protein"] >= 90
    assert r.status != "infeasible" and not any("protein" in i for i in r.issues)
