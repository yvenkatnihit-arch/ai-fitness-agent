"""The meal pool built from the REAL foods in the database: every diet must be able to make every meal."""

import pytest

from app.calc.meal_pool import ALLOWED_DIET_CLASSES, SLOTS, build_pool
from app.db import admin_transaction
from app.db.meal_foods import list_pool_foods

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def foods():
    with admin_transaction("test: read foods") as conn:
        return list_pool_foods(conn)


def test_the_reader_returns_foods_with_units_and_synonyms(foods):
    assert len(foods) >= 170
    by_key = {f.key: f for f in foods}
    assert dict(by_key["roti"].units).get("piece") and by_key["toor_dal"].kcal > 0
    assert any(f.synonyms for f in foods) and all(f.category for f in foods)


@pytest.mark.parametrize("diet", list(ALLOWED_DIET_CLASSES))
def test_every_diet_can_fill_every_required_role_of_every_meal(foods, diet):
    pool = build_pool(foods, diet)
    for slot in SLOTS:
        assert pool[slot].missing == (), (diet, slot, pool[slot].missing)


@pytest.mark.parametrize("diet", ["vegetarian", "eggetarian", "non_vegetarian"])
def test_these_diets_have_enough_choice_everywhere(foods, diet):
    pool = build_pool(foods, diet)
    assert all(pool[slot].thin == () for slot in SLOTS), {s: pool[s].thin for s in SLOTS}


def test_the_vegan_pool_is_known_to_be_thin_so_plans_will_repeat(foods):
    """A data gap, pinned on purpose: more vegan dishes (sabzis, dals) are needed for a varied vegan week."""
    pool = build_pool(foods, "vegan")
    assert pool["lunch"].thin == ("side",)
    assert len(pool["lunch"].roles["protein"]) <= 5 and len(pool["lunch"].roles["vegetable"]) <= 4


def test_no_diet_ever_sees_a_food_it_cannot_eat(foods):
    by_key = {f.key: f for f in foods}
    for diet, allowed in ALLOWED_DIET_CLASSES.items():
        pool = build_pool(foods, diet)
        for slot in pool.values():
            for items in slot.roles.values():
                assert all(by_key[f.key].diet_class in allowed for f in items), diet


def test_a_dislike_removes_the_dish_from_every_meal(foods):
    pool = build_pool(foods, "vegetarian", dislikes=["rajma"])
    names = {f.name.casefold() for slot in pool.values() for items in slot.roles.values() for f in items}
    assert not any("rajma" in n for n in names)
