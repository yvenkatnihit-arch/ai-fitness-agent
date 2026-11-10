"""Step 7.10d-3 (D-093): the protein-dense foods are in the meal roles, and the protein reached on the real foods does not silently drop.
Offline: real validated data, code picks (deterministic), no model, no database."""

import logging

import pytest

from app.calc.meal_pool import BREAKFAST_EXTRA, PROTEIN, SNACK, build_pool
from evals import protein_report as pr

logging.disable(logging.WARNING)
FOODS = pr.pool_foods()


# ---------- the roles ----------

def test_plain_tofu_halloumi_and_the_greek_yogurts_are_in_the_roles_that_can_use_them():
    assert {"tofu", "halloumi", "paneer", "egg"} <= PROTEIN.keys and "dish_protein" in PROTEIN.categories
    assert {"greek_yogurt_lowfat", "greek_yogurt"} <= SNACK.keys and {"greek_yogurt_lowfat", "greek_yogurt"} <= BREAKFAST_EXTRA.keys


def keys(pool, slot, role):
    return {f.key for f in pool[slot].roles[role]}


def test_the_indian_pool_gets_the_new_protein_options_but_not_mediterranean_only_ones():
    pool = build_pool(FOODS, "vegetarian", cuisines=["indian"])
    assert {"tofu", "paneer", "paneer_bhurji", "paneer_tikka"} <= keys(pool, "lunch", "protein")
    assert {"greek_yogurt_lowfat"} <= keys(pool, "evening_snack", "snack") | keys(pool, "breakfast", "extra")
    offered = keys(pool, "lunch", "protein") | keys(pool, "evening_snack", "snack") | keys(pool, "breakfast", "extra")
    assert not ({"halloumi", "mujaddara", "falafel", "greek_yogurt"} & offered)       # tagged Mediterranean only


def test_the_mediterranean_pool_gets_halloumi_and_the_yogurts():
    pool = build_pool(FOODS, "vegetarian", cuisines=["mediterranean"])
    assert "halloumi" in keys(pool, "dinner", "protein")
    assert {"greek_yogurt_lowfat", "greek_yogurt"} <= keys(pool, "evening_snack", "snack")
    assert "tofu" not in keys(pool, "dinner", "protein")                       # tofu is tagged Indian only


def test_a_vegan_never_gets_dairy_or_egg_from_the_new_options():
    pool = build_pool(FOODS, "vegan", cuisines=["indian", "mediterranean"])
    allowed = {f.key for slot in pool.values() for role in slot.roles.values() for f in role}
    assert not allowed & {"halloumi", "paneer", "greek_yogurt_lowfat", "greek_yogurt", "egg_white_omelette", "egg_bhurji", "paneer_bhurji", "paneer_tikka"}
    assert {"tofu", "tofu_bhurji", "protein_chilla"} <= allowed


# ---------- the numbers ----------
# Floors are about 4 points under the value measured when batch 3 was added (mean percent of the protein target over the week). A drop below
# one means a change made plans worse for protein: raise the floor deliberately when plans get better, never lower it to hide a drop.
FLOORS = [
    ("indian", "fat-loss woman", "vegan", 70), ("indian", "fat-loss woman", "vegetarian", 77), ("indian", "fat-loss woman", "eggetarian", 80),
    ("indian", "fat-loss woman", "non_vegetarian", 86), ("indian", "muscle-gain man", "vegetarian", 93),
    ("mediterranean", "fat-loss woman", "vegetarian", 63), ("mediterranean", "fat-loss woman", "non_vegetarian", 90), ("mediterranean", "muscle-gain man", "vegetarian", 88),
]


@pytest.mark.parametrize("cuisine, who, diet, floor", FLOORS)
def test_protein_reached_does_not_drop(cuisine, who, diet, floor):
    r = pr.measure_one(FOODS, cuisine, who, diet)
    assert r.mean >= floor, f"{cuisine} {who} {diet}: mean {r.mean:.0f}% is below the floor {floor}%"


def test_the_known_weak_spot_is_recorded_not_hidden():
    """Vegan Mediterranean cannot get near the protein target of a woman cutting on 1,400 kcal (D-092, D-093). If this ever passes 65% the
    numbers have really improved, and the decision on the protein target should be revisited."""
    r = pr.measure_one(FOODS, "mediterranean", "fat-loss woman", "vegan")
    assert r.mean < 65
