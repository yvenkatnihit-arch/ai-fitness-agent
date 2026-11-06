import pytest

from fooddata import units as u
from fooddata.usda import portion_text

FOODS = {"egg": ("usda_sr_legacy", "171287"), "sambar": ("uk_cofid", "12-467"), "idli": ("computed", "idli"),
         "banana": ("usda_sr_legacy", "173944")}
PORTIONS = {
    "171287": [("1 large", 50.0), ("1 medium", 44.0)],
    "172921": [("1 cup (8 fl oz)", 241.0)],
    "170472": [("0.5 cup", 91.0)],
    "173944": [('1 medium (7" to 7-7/8" long)', 118.0), ("1 cup, sliced", 150.0)],
}
RECIPES = {"idli"}


def row(**changes) -> dict:
    base = dict(key="egg", unit="piece", method="usda", ref="self", ref_portion="1 large", ref_grams="50", note="")
    return {**base, **changes}


def check(**changes) -> u.Unit:
    return u.check_unit(row(**changes), FOODS, PORTIONS, RECIPES)


def test_usda_portion_is_copied_with_its_source():
    unit = check()
    assert unit.grams == 50 and "USDA SR Legacy 171287: 1 large = 50 g" in unit.source


def test_portion_with_a_size_note_matches_its_short_name():
    assert check(key="banana", ref_portion="1 medium", ref_grams="118").grams == 118


def test_katori_is_volume_times_a_measured_density():
    # 150 ml x 241 g / 236.6 ml = 152.8 g
    unit = check(key="sambar", unit="katori", method="volume", ref="172921", ref_portion="1 cup", ref_grams="241")
    assert unit.grams == pytest.approx(152.8)
    # half-cup portions are scaled: 150 ml x 91 g / 118.3 ml = 115.4 g
    unit = check(key="sambar", unit="katori", method="volume", ref="170472", ref_portion="0.5 cup", ref_grams="91")
    assert unit.grams == pytest.approx(115.4)


def test_recipe_piece_uses_our_recipe():
    unit = check(key="idli", method="recipe", ref="idli", ref_portion="1 idli", ref_grams="40")
    assert unit.grams == 40 and "our recipe" in unit.source


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (dict(ref_grams="55"), "no portion"),                         # a number USDA never measured
        (dict(ref_portion="1 jumbo"), "no portion"),                  # a portion USDA doesn't have
        (dict(ref_portion="1"), "no portion"),                        # '1' must not match '1 large' by prefix
        (dict(key="ragi"), "not a validated food"),
        (dict(unit="bucket"), "unknown unit"),
        (dict(method="guess"), "unknown method"),
        (dict(key="sambar"), "needs a USDA food"),                    # 'self' on a CoFID food
        (dict(unit="katori"), "volume unit"),                         # katori must go through 'volume'
        (dict(method="volume", ref_portion="1 large"), "only for"),   # pieces have no volume
        (dict(key="idli", method="recipe", ref="vada"), "not found"),
        (dict(ref_grams="lots"), "not a number"),
    ],
)
def test_wrong_rows_are_blocked_with_a_reason(change, message):
    with pytest.raises(ValueError, match=message):
        check(**change)


def test_volume_needs_a_cup_portion():
    with pytest.raises(ValueError, match="cup portion"):
        u.cup_amount("1 large")


def test_duplicates_and_errors_are_collected_not_raised():
    rows = [row(), row(), row(ref_grams="55")]
    units, errors = u.build_units(FOODS, PORTIONS, RECIPES, rows)
    assert len(units) == 1 and len(errors) == 2
    assert "listed twice" in errors[0]


def test_usda_portion_text():
    assert portion_text("1.0", "cup", "") == "1 cup"
    assert portion_text("1", "undetermined", "medium") == "1 medium"
    assert portion_text("0.5", "cup", "  (8 fl oz) ") == "0.5 cup (8 fl oz)"


def test_unit_names_match_the_database_constraint():
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[3] / "supabase/migrations/20261105140000_reference_tables.sql").read_text()
    for unit in u.DB_UNITS:
        assert f"'{unit}'" in sql
