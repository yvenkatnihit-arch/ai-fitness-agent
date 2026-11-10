"""Step 7.10c (D-090): the `cuisines` column in the food data pipeline (build, recipes, validated file, loader gate)."""

import csv

import pytest

from fooddata import build, cuisines as c, load, recipes
from fooddata.build import review_row
from fooddata.records import FoodRecord

LENTILS = FoodRecord(source="usda_sr_legacy", source_id="172420", name="Lentils, raw", category="Legumes",
                     kcal=352, protein_g=24.6, carbs_g=63.4, fat_g=1.1, fiber_g=10.7, carb_basis="by_difference")
INDEX = {(LENTILS.source, LENTILS.source_id): LENTILS}


def row(**changes) -> dict:
    base = dict(key="masoor_whole", name="Masoor (whole lentils)", local_names="sabut masoor", category="pulse", diet_class="vegan",
                source="usda_sr_legacy", source_id="172420", check_source="", check_id="", match="exact", note="", cuisines="indian")
    return {**base, **changes}


# ---------- parsing ----------

@pytest.mark.parametrize("value, expected", [
    ("indian", ("indian",)), ("mediterranean", ("mediterranean",)), ("indian; Mediterranean ", ("indian", "mediterranean")),
    ("", ("indian",)), (None, ("indian",)), (" ; ", ("indian",)),
])
def test_parse(value, expected):
    assert c.parse(value) == expected
    assert c.to_cell(c.parse(value)) == ";".join(expected)


@pytest.mark.parametrize("value, ok", [("indian", True), ("indian;mediterranean", True), ("", True), (None, True), ("martian", False),
                                       ("indian;indian", False), ("indian;martian", False)])
def test_problems(value, ok):
    assert (c.problems(value) == []) is ok


def test_the_planned_cuisines_include_every_enabled_one():
    from app.core.vocabulary import CUISINES
    assert set(CUISINES) <= set(c.PLANNED)               # the app can never enable a cuisine the pipeline does not know


# ---------- build ----------

def test_a_row_with_a_known_cuisine_is_fine_and_an_unknown_one_is_blocked():
    assert review_row(row(cuisines="indian;mediterranean"), INDEX).status == "ready"
    bad = review_row(row(cuisines="martian"), INDEX)
    assert bad.status == "blocked" and any(i.check == "cuisines" for i in bad.issues)


def test_a_row_without_the_column_counts_as_indian_so_old_callers_still_work():
    r = row()
    del r["cuisines"]
    assert review_row(r, INDEX).status == "ready"


def test_the_source_files_have_the_new_column_last_and_every_row_has_a_valid_value():
    ingredients = build.read_ingredients()
    assert build.COLUMNS[-1] == "cuisines" and recipes.RECIPE_COLUMNS[-1] == "cuisines"
    assert all(c.problems(r["cuisines"]) == [] for r in ingredients)
    recipe_rows, _ = recipes.read_recipes()
    assert all(c.problems(r["cuisines"]) == [] for r in recipe_rows)


def test_the_validated_file_carries_the_cuisines():
    with build.VALIDATED.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert "cuisines" in rows[0] and all(c.problems(r["cuisines"]) == [] for r in rows)


# ---------- loader ----------

def validated_row(**changes) -> dict:
    base = dict(key="x", name="X", local_names="", category="pulse", diet_class="vegan", source="usda_sr_legacy", source_id="1",
                kcal="100", protein_g="5", carbs_g="10", fat_g="1", fiber_g="2", status="ready", cuisines="indian")
    return {**base, **changes}


def test_the_loader_reads_the_cuisines_and_defaults_to_indian():
    assert load.to_food_row(validated_row(cuisines="indian;mediterranean")).cuisines == ("indian", "mediterranean")
    old = validated_row()
    del old["cuisines"]
    assert load.to_food_row(old).cuisines == ("indian",)


def test_the_loader_refuses_an_unknown_cuisine_with_a_clear_message():
    with pytest.raises(ValueError, match="unknown cuisine"):
        load.to_food_row(validated_row(cuisines="martian"))


@pytest.fixture
def only_indian_enabled(monkeypatch):
    """The loader gate is about ANY cuisine the app has not enabled yet; Mediterranean is live (D-094), so pretend only Indian is."""
    monkeypatch.setattr("app.core.vocabulary.CUISINES", ("indian",))


def test_a_food_is_loaded_with_only_its_enabled_cuisines_and_one_with_none_is_held_back(only_indian_enabled):
    foods = [load.to_food_row(validated_row(key="a")), load.to_food_row(validated_row(key="b", cuisines="mediterranean")),
             load.to_food_row(validated_row(key="c", cuisines="indian;mediterranean"))]
    loadable, waiting = load.split_by_enabled(foods)
    assert [(f.key, f.cuisines) for f in loadable] == [("a", ("indian",)), ("c", ("indian",))]     # c stays Indian until the other is enabled
    assert waiting == {"mediterranean": ["b"]}                                                    # b has no enabled cuisine: held back
    assert load.split_by_enabled(foods[:1]) == ([foods[0]], {})


def test_the_loader_reports_what_it_holds_back_and_loads_the_rest(monkeypatch, capsys, only_indian_enabled):
    rows = [load.to_food_row(validated_row(key="hummus", cuisines="mediterranean")), load.to_food_row(validated_row(key="dal"))]
    monkeypatch.setattr(load, "read_validated", lambda: rows)
    class Done(Exception):
        pass

    def fake_connect(*a, **k):
        raise Done                                    # stop at the first database call: we only want to see what was selected

    monkeypatch.setattr(load.psycopg, "connect", fake_connect)
    monkeypatch.setattr("sys.argv", ["load"])
    with pytest.raises(Done):
        load.main()
    out = capsys.readouterr().out
    assert "HELD BACK" in out and "mediterranean" in out and "hummus" in out and "dal" not in out.split("HELD BACK")[1]


def test_the_upsert_writes_the_cuisines_column():
    assert "cuisines" in load.UPSERT and "cuisines = excluded.cuisines" in load.UPSERT


def test_the_real_validated_file_can_always_be_loaded_today(monkeypatch):
    """With every enabled cuisine the whole file loads; with only Indian enabled, the Mediterranean-only foods wait (the gate still works)."""
    foods = load.read_validated()
    everything, none_waiting = load.split_by_enabled(foods)
    assert none_waiting == {} and len(everything) == len(foods)                  # Mediterranean is enabled (D-094)
    import app.core.vocabulary as vocab
    monkeypatch.setattr(vocab, "CUISINES", ("indian",))
    loadable, waiting = load.split_by_enabled(foods)
    assert set(waiting) <= {"mediterranean"}
    assert len(loadable) + sum(len(v) for v in waiting.values()) == len(foods)
    assert all(f.cuisines == ("indian",) for f in loadable)
    assert len(loadable) >= 179                                             # every Indian food from before is still loadable


def test_units_follow_their_foods_so_held_back_foods_leave_no_orphan_units():
    from fooddata.units import Unit
    units = [Unit("dal", "katori", 150.0, "x"), Unit("falafel", "piece", 27.0, "x"), Unit("dal", "tbsp", 15.0, "x")]
    keep, skipped = load.units_of_loaded_foods(units, {"dal"})
    assert [(u.key, u.unit) for u in keep] == [("dal", "katori"), ("dal", "tbsp")] and skipped == 1
    assert load.units_of_loaded_foods(units, {"dal", "falafel"}) == (units, 0)


def test_the_real_unit_file_has_no_unit_the_loader_would_choke_on(only_indian_enabled):
    """What `fooddata.load` really does: keep only the units of loadable foods, then every one of them must have a loaded food."""
    loadable, _ = load.split_by_enabled(load.read_validated())
    keys = {f.key for f in loadable}
    keep, skipped = load.units_of_loaded_foods(load.read_units(), keys)
    assert {u.key for u in keep} <= keys and skipped > 0                 # the Mediterranean units are skipped while the cuisine waits
