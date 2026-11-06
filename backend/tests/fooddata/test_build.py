import pytest

from fooddata.build import COLUMNS, read_ingredients, review_row
from fooddata.records import CarbParts, FoodRecord

LENTILS = FoodRecord(source="usda_sr_legacy", source_id="172420", name="Lentils, raw", category="Legumes",
                     kcal=352, protein_g=24.6, carbs_g=63.4, fat_g=1.1, fiber_g=10.7, carb_basis="by_difference")
CHICKEN = FoodRecord(source="usda_sr_legacy", source_id="171509", name="Chicken, broilers or fryers, breast, raw",
                     category="Poultry Products", kcal=108, protein_g=20.3, carbs_g=0, fat_g=3.0, fiber_g=0,
                     carb_basis="by_difference")
COFID_LENTILS = FoodRecord(source="uk_cofid", source_id="13-089", name="Lentils, green and brown, raw", category="DG",
                           kcal=297, protein_g=24.3, carbs_g=45.0, fat_g=1.9, fiber_g=8.9, carb_basis="available",
                           carb_parts=CarbParts(starch_g=44.0, total_sugars_g=1.0, mono_sugars_g=0.2, di_sugars_g=0.8))
INDEX = {(f.source, f.source_id): f for f in (LENTILS, CHICKEN, COFID_LENTILS)}


def row(**changes) -> dict:
    base = dict(key="masoor_whole", name="Masoor (whole lentils)", local_names="sabut masoor", category="pulse",
                diet_class="vegan", source="usda_sr_legacy", source_id="172420", check_source="", check_id="",
                match="exact", note="")
    return {**base, **changes}


def test_exact_clean_mapping_is_ready_with_converted_carbs():
    result = review_row(row(), INDEX)
    assert result.status == "ready"
    assert result.carbs_g == pytest.approx(52.7)  # 63.4 - 10.7 (D-038)


def test_close_match_always_goes_to_review():
    assert review_row(row(match="close"), INDEX).status == "review"


def test_unknown_source_id_is_blocked():
    result = review_row(row(source_id="999999"), INDEX)
    assert result.status == "blocked" and "not found" in result.issues[0].message


def test_meat_mapped_as_vegetarian_is_blocked():
    # A mislabelled mapping must never reach a vegetarian's plan.
    result = review_row(row(key="x", name="Chicken breast", source_id="171509", diet_class="vegetarian"), INDEX)
    assert result.status == "blocked"
    assert any(i.check == "diet_class" for i in result.issues)


def test_our_own_name_is_also_checked():
    # Source name looks plant-based, but our name says paneer: labelling it vegan is caught.
    result = review_row(row(name="Paneer", local_names=""), INDEX)
    assert result.status == "blocked"


def test_gap_is_recorded_not_substituted():
    result = review_row(row(key="ragi", source="", source_id="", match="none", note="GAP"), INDEX)
    assert result.status == "gap" and result.food is None


def test_cross_check_disagreement_goes_to_review():
    # USDA 352 kcal vs CoFID 297 kcal: 16 % apart -> fine; force a big gap to see the warning
    far = FoodRecord(**{**COFID_LENTILS.__dict__, "source_id": "far", "kcal": 150})
    index = {**INDEX, ("uk_cofid", "far"): far}
    assert review_row(row(check_source="uk_cofid", check_id="13-089"), index).status == "ready"
    assert review_row(row(check_source="uk_cofid", check_id="far"), index).status == "review"


def test_missing_cross_check_id_is_blocked():
    assert review_row(row(check_source="uk_cofid", check_id="nope"), INDEX).status == "blocked"


def test_bad_diet_class_or_match_values_are_blocked():
    assert review_row(row(diet_class="veg"), INDEX).status == "blocked"
    assert review_row(row(match="maybe"), INDEX).status == "blocked"


# --- The real data/ingredients.csv file ---

def test_ingredients_file_is_well_formed():
    rows = read_ingredients()
    assert len(rows) >= 50
    for r in rows:
        assert set(r) == set(COLUMNS), r["key"]
        if r["match"] == "none":
            assert not r["source"] and r["note"].startswith("GAP"), r["key"]
        else:
            assert r["source"] and r["source_id"], r["key"]
