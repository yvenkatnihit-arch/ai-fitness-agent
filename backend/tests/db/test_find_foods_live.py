"""Step 8.3 (D-107): the food ranking tool against the real food database. No model is called."""

import pytest

from app.agents.context import RunContext
from app.agents.food_tools import FIND_FOODS, FindFoodsArgs
from app.db import admin_transaction
from tests.db.test_onboarding_complete import FORMS, client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


def find(user, **kw):
    return FIND_FOODS.run(RunContext(user), FindFoodsArgs(**kw))


def diet_classes(keys):
    with admin_transaction("test: diet classes") as conn:
        return {k: c for k, c in conn.execute("select key, diet_class from public.foods where key = any(%s)", (list(keys),)).fetchall()}


def test_the_most_protein_ranking_is_sorted_from_the_database_values_and_labelled_per_100_g(client, users):
    onboard(client)                                                                        # a vegetarian Indian user
    got = find(users[0], sort_by="most_protein", limit=8)
    proteins = [f["protein_g"] for f in got["foods"]]
    assert got["values_are"] == "per 100 g" and got["diet"] == "vegetarian" and len(proteins) == 8
    assert proteins == sorted(proteins, reverse=True)
    with admin_transaction("test: raw values") as conn:
        stored = dict(conn.execute("select key, protein_g_per_100g from public.foods where key = any(%s)", ([f["key"] for f in got["foods"]],)).fetchall())
    assert all(float(stored[f["key"]]) == f["protein_g"] for f in got["foods"])             # exactly what is stored


def test_a_vegetarian_is_never_shown_meat_fish_or_egg(client, users):
    onboard(client)
    shown = find(users[0], sort_by="most_protein", limit=8)["foods"] + find(users[0], sort_by="most_protein_per_calorie", limit=8)["foods"]
    assert shown and set(diet_classes({f["key"] for f in shown}).values()) <= {"vegan", "vegetarian"}


def test_asking_about_another_diet_shows_that_diet_and_a_non_vegetarian_sees_meat(client, users):
    onboard(client)
    vegan = find(users[0], sort_by="most_protein", diet="vegan", limit=8)
    assert vegan["diet"] == "vegan" and set(diet_classes({f["key"] for f in vegan["foods"]}).values()) == {"vegan"}
    non_veg = find(users[0], sort_by="most_protein", diet="non_vegetarian", kind="ingredients", limit=8)
    assert "non_vegetarian" in set(diet_classes({f["key"] for f in non_veg["foods"]}).values())     # plain meat and fish are ranked too


def test_a_dislike_removes_the_food_and_the_filters_work(client, users):
    onboard(client)
    top = find(users[0], sort_by="most_protein", kind="ingredients", limit=1)["foods"][0]
    client.patch("/profile", json={"disliked_foods": [top["name"].split()[0]]})
    after = find(users[0], sort_by="most_protein", kind="ingredients", limit=8)["foods"]
    assert top["key"] not in {f["key"] for f in after}
    low = find(users[0], sort_by="most_protein", max_kcal=120, min_protein_g=2, limit=8)["foods"]
    assert low and all(f["kcal"] <= 120 and f["protein_g"] >= 2 for f in low)
    least = [f["kcal"] for f in find(users[0], sort_by="least_calories", limit=5)["foods"]]
    assert least == sorted(least)


def test_cuisines_narrow_the_own_diet_ranking_but_not_a_question_about_another_diet(client, users):
    onboard(client)
    client.patch("/profile", json={"cuisines": ["mediterranean"]})
    own = find(users[0], sort_by="most_protein", limit=8)["foods"]
    with admin_transaction("test: cuisines") as conn:
        cuisines = dict(conn.execute("select key, cuisines from public.foods where key = any(%s)", ([f["key"] for f in own],)).fetchall())
    assert own and all("mediterranean" in c for c in cuisines.values())


def test_a_user_with_no_diet_saved_is_asked_instead_of_guessed_for(client, users):
    got = find(users[1], sort_by="most_protein")                                           # never onboarded
    assert "error" in got and "diet" in got["error"].lower()
    assert find(users[1], sort_by="most_protein", diet="vegan")["foods"]                   # but an explicit diet question still works


def test_snacks_are_snack_foods_and_the_dry_ingredient_note_is_given_when_ingredients_can_appear(client, users):
    onboard(client)
    snacks = find(users[0], sort_by="least_calories", kind="snacks", limit=8)
    with admin_transaction("test: categories") as conn:
        categories = {c for (c,) in conn.execute("select category from public.foods where key = any(%s)", ([f["key"] for f in snacks["foods"]],)).fetchall()}
    assert snacks["foods"] and categories <= {"fruit", "nut_seed", "dairy", "egg", "dish_snack", "dish_dip"}
    assert "note" in snacks and "dry" in snacks["note"]
    assert "note" not in find(users[0], sort_by="most_protein", kind="dishes")                           # a dishes ranking needs no such warning
