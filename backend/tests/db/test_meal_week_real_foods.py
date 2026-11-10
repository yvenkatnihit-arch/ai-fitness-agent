"""The 7-day meal workflow on the REAL foods with REAL engine targets, with the model switched off (code fallback only).

Free of Gemini and deterministic: this proves the safety net itself always yields a complete, safe week.
"""

import pytest

from app.calc.engine import BodyProfile, calculate_targets
from app.calc.meal_pool import ALL_SLOTS, ALLOWED_DIET_CLASSES, SLOTS, build_pool
from app.calc.meal_solver import day_targets
from app.calc.meal_week import emphasis_for, validate_day
from app.db import admin_transaction
from app.db.meal_foods import list_pool_foods
from app.llm.client import LLMBusy
from app.workflows.pick_meals import pick_meals

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
    "kidney_m": BodyProfile(weight_kg=82, height_cm=176, age_years=50, sex="male", activity_level="moderate",
                            goal="fat_loss", screening_flags=frozenset({"kidney"}), pace="normal"),
}


def down(prompt):
    raise LLMBusy()


@pytest.fixture(scope="module")
def foods():
    with admin_transaction("test: read foods") as conn:
        return list_pool_foods(conn)


def make_week(foods, diet, name, dislikes=()):
    profile = PROFILES[name]
    engine = calculate_targets(profile)
    targets = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    emphasis = emphasis_for(engine.protein_g, engine.calorie_target_kcal, profile.screening_flags)
    return pick_meals(foods, diet, list(dislikes), targets, profile.goal, emphasis, ask=down, cuisines=INDIAN), targets, engine


@pytest.mark.parametrize("diet", list(ALLOWED_DIET_CLASSES))
@pytest.mark.parametrize("name", list(PROFILES))
def test_every_diet_and_profile_gets_a_complete_safe_week(foods, diet, name):
    plan, targets, engine = make_week(foods, diet, name)
    assert [d.day for d in plan.days] == list(range(1, 8))
    pool = build_pool(foods, diet, slots=plan.slots, cuisines=INDIAN)
    for d in plan.days:
        assert d.solution.status in ("ok", "issues")
        assert targets.kcal_min - TOL <= d.solution.totals.kcal <= targets.kcal_max + TOL
        assert d.solution.totals.protein_g <= targets.protein_max_g + TOL
        assert validate_day(d.picks, pool, plan.slots) == []
        assert all(i.portion.grams > 0 for i in d.solution.items)


def test_a_3000_kcal_day_now_fits_with_a_mid_morning_meal_and_bigger_portions(foods):
    """RESOLVED (it was pinned as infeasible in step 6.7b): five meals and scaled portions make big days work."""
    for diet in ("vegetarian", "non_vegetarian"):
        plan, targets, engine = make_week(foods, diet, "muscle_m")
        assert engine.calorie_target_kcal > 2800
        assert plan.slots == ALL_SLOTS and plan.portion_scale > 1.3
        assert all(d.solution.status != "infeasible" and "mid_morning" in d.picks for d in plan.days)
        assert all(2860 <= d.solution.totals.kcal <= 3140 for d in plan.days)


def test_the_four_meal_skeleton_still_cannot_reach_3000_kcal(foods):
    """Why the fifth meal exists: with four meals and unscaled portions a 3,000 kcal day is never a clean day. (It was infeasible, about 2,300
    kcal at most; since the protein batch, D-093, added bigger dishes it can be reached but only with issues.)"""
    from app.calc.meal_solver import MealItem, solve_day
    profile = PROFILES["muscle_m"]
    engine = calculate_targets(profile)
    t = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
    pool = build_pool(foods, "vegetarian", cuisines=INDIAN)
    items = [MealItem(s, r, c[0]) for s in SLOTS for r, c in pool[s].roles.items() if c]
    assert solve_day(items, t).status != "ok"


def test_the_kidney_user_stays_at_or_under_their_protein_cap_every_day(foods):
    plan, targets, engine = make_week(foods, "vegetarian", "kidney_m")
    assert plan.emphasis == "low_protein"
    assert all(d.solution.totals.protein_g <= engine.protein_g + TOL for d in plan.days)        # the SAFETY limit: never above the cap
    assert all(d.solution.status != "infeasible" for d in plan.days)
    # Soft issues are allowed (the protein batch can leave one day with a light snack: 'evening_snack has 51 kcal but should have about
    # 234'), but never an issue about protein or total calories.
    assert not any("protein" in i or "kcal a day" in i for d in plan.days for i in d.solution.issues)
    assert sum(d.solution.status == "ok" for d in plan.days) >= 5


def test_a_healthy_diet_has_variety_across_the_week(foods):
    plan, _, _ = make_week(foods, "vegetarian", "maintain_o")
    assert len({d.picks["lunch"]["protein"] for d in plan.days}) >= 5
    assert len({d.picks["breakfast"]["main"] for d in plan.days}) >= 4


def test_the_thin_vegan_pool_is_reported_so_the_screen_can_say_so(foods):
    plan, _, _ = make_week(foods, "vegan", "maintain_o")
    assert set(plan.thin_roles) == {"lunch", "dinner"} and "side" in plan.thin_roles["lunch"]


def test_a_dislike_never_appears_in_any_meal(foods):
    plan, _, _ = make_week(foods, "vegetarian", "maintain_o", dislikes=["paneer", "rajma"])
    names = {i.food_name.casefold() for d in plan.days for i in d.solution.items}
    assert not any("paneer" in n or "rajma" in n for n in names)


def test_the_same_inputs_give_the_same_week(foods):
    a, _, _ = make_week(foods, "eggetarian", "fatloss_f")
    b, _, _ = make_week(foods, "eggetarian", "fatloss_f")
    assert [d.picks for d in a.days] == [d.picks for d in b.days]
