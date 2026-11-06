import pytest

from fooddata.carbs import available_carbs
from fooddata.records import CarbParts, FoodRecord


def usda(**changes) -> FoodRecord:
    base = dict(source="usda_sr_legacy", source_id="1", name="Lentils, raw", category=None, kcal=352,
                protein_g=24.6, carbs_g=63.4, fat_g=1.1, fiber_g=10.7, carb_basis="by_difference")
    return FoodRecord(**{**base, **changes})


def cofid(parts: CarbParts | None, carbs_g=20.0) -> FoodRecord:
    return FoodRecord(source="uk_cofid", source_id="x", name="Test", category=None, kcal=100, protein_g=3,
                      carbs_g=carbs_g, fat_g=1, fiber_g=2, carb_basis="available", carb_parts=parts)


# --- USDA: total minus fibre ---

def test_usda_lentils_hand_worked():
    result = available_carbs(usda())
    assert result.grams == pytest.approx(63.4 - 10.7)  # 52.7 g
    assert result.quality == "exact"


def test_usda_without_fibre_is_not_guessed():
    result = available_carbs(usda(fiber_g=None))
    assert result.grams is None and "fibre unknown" in result.note


def test_usda_tiny_negative_from_rounding_becomes_zero():
    assert available_carbs(usda(carbs_g=1.0, fiber_g=1.3)).grams == 0.0


def test_usda_fibre_far_above_carbs_is_flagged():
    assert available_carbs(usda(carbs_g=1.0, fiber_g=5.0)).grams is None


# --- CoFID: monosaccharide equivalents back to weight eaten ---

def test_cofid_exact_conversion_hand_worked():
    # 11 g starch (/1.10 = 10) + 2 g mono + 4.2 g di (/1.05 = 4) + 1.1 g oligo (/1.10 = 1) = 17 g
    parts = CarbParts(starch_g=11.0, oligo_g=1.1, total_sugars_g=6.2, mono_sugars_g=2.0, di_sugars_g=4.2)
    result = available_carbs(cofid(parts))
    assert result.grams == pytest.approx(17.0)
    assert result.quality == "exact"


def test_cofid_pure_sugar_ends_up_at_100g_not_105():
    # Table sugar: 105 g sucrose as monosaccharide equivalents -> 100 g as eaten
    parts = CarbParts(starch_g=0.0, oligo_g=None, total_sugars_g=105.0, mono_sugars_g=0.0, di_sugars_g=105.0)
    assert available_carbs(cofid(parts, carbs_g=105.0)).grams == pytest.approx(100.0)


def test_cofid_approximate_when_sugar_breakdown_unknown():
    # 22 g starch (/1.10 = 20) + 2.1 g sugars (/1.05 = 2) = 22 g, marked approximate
    parts = CarbParts(starch_g=22.0, total_sugars_g=2.1, mono_sugars_g=None, di_sugars_g=None)
    result = available_carbs(cofid(parts))
    assert result.grams == pytest.approx(22.0)
    assert result.quality == "approximate"


def test_cofid_without_breakdown_is_not_guessed():
    result = available_carbs(cofid(CarbParts(starch_g=None, total_sugars_g=None)))
    assert result.grams is None and "unknown" in result.note


def test_cofid_zero_carbs_needs_no_breakdown():
    assert available_carbs(cofid(None, carbs_g=0.0)).grams == 0.0  # e.g. oils


def test_missing_carbs_entirely():
    assert available_carbs(usda(carbs_g=None)).grams is None
