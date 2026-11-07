"""Household portion rules for meal plans (pure Python). Separate from tests/test_portions.py (meal logging)."""

import pytest

from app.calc.meal_pool import PoolFood
from app.calc.meal_portions import describe, portion_spec


def food(key, category, units=(), kcal=100.0):
    return PoolFood(id=1, key=key, name=key, category=category, diet_class="vegan", kcal=kcal, protein_g=5, carbs_g=15,
                    fat_g=2, review_status="ready", units=tuple(units))


@pytest.mark.parametrize("f,expected", [
    # (step g, min steps, max steps, unit, steps per unit)
    (food("roti", "dish_bread", [("piece", 43.0)]), (43.0, 1, 4, "piece", 1)),
    (food("rice", "dish_rice", [("katori", 150.0)]), (75.0, 1, 6, "katori", 2)),                 # 0.5 to 3 katori
    (food("toor_dal", "dish_dal", [("katori", 150.0)]), (75.0, 1, 4, "katori", 2)),              # 0.5 to 2 katori
    (food("idli", "dish_breakfast", [("piece", 40.0), ("katori", 120.0)]), (40.0, 1, 5, "piece", 1)),   # piece first
    (food("egg", "egg", [("piece", 50.0)]), (50.0, 1, 4, "piece", 1)),
    (food("boiled_egg", "dish_side", [("piece", 50.0), ("katori", 100.0)]), (50.0, 1, 4, "piece", 1)),  # by key
    (food("banana", "fruit", [("piece", 120.0)]), (120.0, 1, 2, "piece", 1)),
    (food("milk", "dairy", [("glass", 250.0)]), (125.0, 1, 4, "glass", 2)),
    (food("curd", "dairy", [("katori", 100.0), ("glass", 200.0)]), (50.0, 1, 4, "katori", 2)),   # katori beats glass
    (food("almonds", "nut_seed", [("piece", 1.2)]), (5.0, 2, 8, None, 1)),                  # a 1.2 g piece is not a meal unit
    (food("almonds", "nut_seed"), (5.0, 2, 8, None, 1)),                                         # 10 to 40 g in 5 g steps
    (food("papaya", "fruit"), (10.0, 8, 25, None, 1)),                                           # 80 to 250 g
    (food("mystery", "dish_other"), (10.0, 6, 30, None, 1)),                                     # 60 to 300 g default
    (food("only_tbsp", "dish_other", [("tbsp", 15.0)]), (10.0, 6, 30, None, 1)),                 # tbsp is not a meal unit
])
def test_portion_rules(f, expected):
    s = portion_spec(f)
    assert (s.step_g, s.min_steps, s.max_steps, s.unit, s.steps_per_unit) == expected


def test_a_katori_food_with_no_piece_never_counts_pieces():
    assert portion_spec(food("dal", "dish_dal", [("piece", 30.0), ("katori", 150.0)])).unit == "katori"


@pytest.mark.parametrize("f,steps,grams,unit,qty,text", [
    (food("roti", "dish_bread", [("piece", 43.0)]), 2, 86.0, "piece", 2, "2 pieces (86 g)"),
    (food("roti", "dish_bread", [("piece", 43.0)]), 1, 43.0, "piece", 1, "1 piece (43 g)"),
    (food("rice", "dish_rice", [("katori", 150.0)]), 3, 225.0, "katori", 1.5, "1.5 katori (225 g)"),
    (food("rice", "dish_rice", [("katori", 150.0)]), 2, 150.0, "katori", 1, "1 katori (150 g)"),
    (food("rice", "dish_rice", [("katori", 150.0)]), 1, 75.0, "katori", 0.5, "0.5 katori (75 g)"),
    (food("milk", "dairy", [("glass", 250.0)]), 3, 375.0, "glass", 1.5, "1.5 glass (375 g)"),
    (food("almonds", "nut_seed"), 4, 20.0, None, None, "20 g"),
    (food("papaya", "fruit"), 15, 150.0, None, None, "150 g"),
])
def test_describe(f, steps, grams, unit, qty, text):
    p = describe(portion_spec(f), steps)
    assert (p.grams, p.unit, p.quantity, p.text) == (grams, unit, qty, text)


def test_describe_refuses_an_amount_outside_the_allowed_range():
    spec = portion_spec(food("roti", "dish_bread", [("piece", 43.0)]))
    for bad in (0, 5, -1):
        with pytest.raises(ValueError):
            describe(spec, bad)


def test_household_units_stay_within_what_the_database_accepts():
    """meal_plan_items: unit in the allowed list, qty numeric(5,2) > 0, grams numeric(6,1) <= 2000."""
    allowed = {"katori", "piece", "cup", "glass", "bowl", "plate", "slice", "tbsp", "tsp", "handful"}
    for f in (food("roti", "dish_bread", [("piece", 43.0)]), food("rice", "dish_rice", [("katori", 150.0)]),
              food("milk", "dairy", [("glass", 250.0)]), food("almonds", "nut_seed")):
        spec = portion_spec(f)
        for steps in range(spec.min_steps, spec.max_steps + 1):
            p = describe(spec, steps)
            assert p.unit is None or p.unit in allowed
            assert p.quantity is None or 0 < p.quantity < 1000
            assert 0 < p.grams <= 2000


@pytest.mark.parametrize("f,role,max_steps", [
    (food("chaas", "dairy", [("glass", 250.0)]), None, 4),         # no role: up to 2 glasses
    (food("chaas", "dairy", [("glass", 250.0)]), "side", 2),       # as a side: at most 1 glass (260 g cap)
    (food("milk", "dairy", [("glass", 250.0)]), "extra", 2),       # a breakfast extra: at most 1 glass
    (food("moong", "dish_side", [("katori", 128.0)]), "snack", 3), # 64 g steps, 300 g cap -> 4 steps allowed by cap but food max is 3
    (food("aloo", "dish_sabzi", [("katori", 115.0)]), "vegetable", 4),   # main roles are not capped
    (food("raita", "dish_side", [("katori", 200.0)]), "side", 2),  # 100 g steps: 2 steps = 200 g <= 260 g
])
def test_side_dishes_extras_and_snacks_are_capped_by_role(f, role, max_steps):
    assert portion_spec(f, role).max_steps == max_steps


def test_a_role_cap_never_goes_below_the_minimum_portion():
    big_piece = food("paratha_big", "dish_bread", [("piece", 300.0)])      # one piece already exceeds the side cap
    s = portion_spec(big_piece, "side")
    assert s.min_steps == s.max_steps == 1
