import pytest

from fooddata.load import read_validated, synonyms_from, to_food_row


def csv_row(**changes) -> dict:
    base = dict(key="curd", name="Curd (plain whole milk)", local_names="dahi;mosaru;thayir", category="dairy",
                diet_class="vegetarian", source="usda_sr_legacy", source_id="171284",
                source_name="Yogurt, plain, whole milk", kcal="61.0", protein_g="3.47", carbs_g="4.66",
                fat_g="3.25", fiber_g="0.0", carbs_quality="exact", match="exact", status="ready")
    return {**base, **changes}


def test_row_becomes_db_values():
    food = to_food_row(csv_row())
    assert (food.key, food.kcal, food.protein_g, food.fiber_g) == ("curd", 61.0, 3.47, 0.0)
    assert food.source_ref == "171284" and food.review_status == "ready" and not food.is_dish
    assert food.synonyms == ("dahi", "mosaru", "thayir")


def test_values_are_rounded_to_the_column_precision():
    food = to_food_row(csv_row(kcal="145.333", carbs_g="27.3456"))
    assert (food.kcal, food.carbs_g) == (145.3, 27.35)


def test_unknown_fibre_stays_unknown_not_zero():
    assert to_food_row(csv_row(fiber_g="")).fiber_g is None


def test_dish_categories_are_dishes():
    assert to_food_row(csv_row(key="idli", category="dish_breakfast")).is_dish


def test_synonyms_are_cleaned():
    assert synonyms_from(" dahi ;;Dahi; curd ", "Curd") == ("dahi",)


@pytest.mark.parametrize(
    "change",
    [{"kcal": "lots"}, {"kcal": "950"}, {"protein_g": "60", "carbs_g": "50"}, {"status": "blocked"}, {"name": ""}],
)
def test_rows_the_table_would_reject_fail_early_with_a_clear_message(change):
    with pytest.raises(ValueError, match="curd"):
        to_food_row(csv_row(**change))


def test_the_real_validated_file_loads_cleanly():
    foods = read_validated()
    assert len(foods) > 100
    assert {f.review_status for f in foods} <= {"ready", "review"}
    assert any(f.source == "computed" for f in foods)  # recipes are included
