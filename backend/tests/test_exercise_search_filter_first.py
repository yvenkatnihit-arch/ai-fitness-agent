"""Step 8.2 (D-106): found in a real chat run. "Which exercises work my chest" said nothing suits a home beginner, because the search cut the
list to the best 8 BEFORE the user's limits were applied, and the best 8 were equipment-heavy. Filter first, cut afterwards. Offline, real library."""

from app.calc.exercise_filter import ExerciseNeeds, why_hidden
from app.calc.exercise_search import search, words
from tests.test_exercise_search import real_library


def test_plurals_find_the_singular_name():
    lib = real_library()
    assert words("squats") == ["squats"] and search(lib, "squats", limit=None)
    assert {o.key for o in search(lib, "squats", limit=None)} >= {o.key for o in search(lib, "squat", limit=None)}
    assert {o.name for o in search(lib, "lunges", limit=None)} == {o.name for o in search(lib, "lunge", limit=None)} and search(lib, "lunges", limit=None)


def test_limit_none_returns_every_match_and_a_number_still_cuts():
    lib = real_library()
    everything = search(lib, "chest", limit=None)
    assert len(everything) == 13 and len(search(lib, "chest", limit=3)) == 3 and len(search(lib, "chest", limit=99)) == 8


def test_a_home_beginner_with_no_equipment_still_gets_the_chest_exercises_that_suit_them():
    needs = ExerciseNeeds("home", "beginner", frozenset(), frozenset())
    suitable = [o for o in search(real_library(), "chest", limit=None) if why_hidden(o, needs) is None]
    assert {o.name for o in suitable} >= {"Push-Up", "Knee Push-Up"}


def test_the_bug_in_miniature_a_suitable_exercise_ranked_below_the_cut_is_still_found_when_everything_is_returned():
    """Nine equipment-heavy exercises outrank the one bodyweight move. Cutting to 8 first loses it; limit=None keeps it for the filter."""
    from tests.test_exercise_search import ex
    heavy = [ex(f"h{i}", f"Chest Machine Press {i}", ["chest"], equipment=("cable_machine",)) for i in range(9)]
    simple = ex("pushup", "Push-Up", ["chest"], difficulty="beginner")
    pool = heavy + [simple]
    assert simple.key not in {o.key for o in search(pool, "chest machine", limit=8)}
    assert "pushup" in {o.key for o in search(pool, "chest", limit=None)}


def test_on_equal_scores_the_easier_exercise_comes_first_then_the_shorter_name():
    names = [o.name for o in search(real_library(), "squats", limit=None)]
    assert names.index("Bodyweight Squat") < names.index("Barbell Back Squat") and names.index("Bodyweight Squat") < names.index("Jump Squat")
    from app.calc.exercise_search import find_by_name
    assert find_by_name(real_library(), "squats").name == "Bodyweight Squat"
