"""Step 8.2 (D-106): searching the exercise library, offline. Includes the REAL validated library (data/exercises_validated.csv)."""

import csv
from pathlib import Path

import pytest

from app.agents.exercise_coach import EXERCISE_SPEC, exercise_registry
from app.agents.menu import default_menu
from app.calc.exercise_filter import ExerciseOption
from app.calc.exercise_search import search, words

LIBRARY = Path(__file__).resolve().parents[2] / "data" / "exercises_validated.csv"


def real_library() -> list[ExerciseOption]:
    rows = list(csv.DictReader(LIBRARY.open(encoding="utf-8")))
    return [ExerciseOption(id=i, key=r["key"], name=r["name"], muscle_groups=tuple(r["muscle_groups"].split(";")),
                           equipment=tuple(x for x in r["equipment"].split(";") if x), location=r["location"], difficulty=r["difficulty"],
                           movement_pattern=r["movement_pattern"], form_cues=tuple(r["form_cues"].split("\n")),
                           contraindications=tuple(x for x in r["contraindications"].split(";") if x), review_status=r["status"])
            for i, r in enumerate(rows)]


def ex(key, name, muscles, equipment=(), pattern="squat", difficulty="beginner", location="both"):
    return ExerciseOption(id=1, key=key, name=name, muscle_groups=tuple(muscles), equipment=tuple(equipment), location=location, difficulty=difficulty,
                          movement_pattern=pattern, form_cues=("a",), contraindications=(), review_status="reviewed")


SMALL = [ex("squat", "Bodyweight Squat", ["quads", "glutes"]), ex("bridge", "Glute Bridge", ["glutes", "hamstrings"], pattern="hinge"),
         ex("pushup", "Push-Up", ["chest", "triceps"], pattern="push_horizontal"), ex("plank", "Plank", ["abs"], pattern="core")]


def test_words_drop_filler_and_map_everyday_names_to_library_muscles():
    assert words("what exercises work my glutes at home") == ["glutes"]
    assert words("how do I train my core") == ["abs"]
    assert words("The BUM, legs and arms") == ["glutes", "quads", "biceps"]


def test_a_name_match_beats_a_muscle_match_and_unmatched_exercises_never_appear():
    names = [o.name for o in search(SMALL, "glute bridge")]
    assert names[0] == "Glute Bridge" and "Push-Up" not in names and "Plank" not in names


def test_a_muscle_word_finds_the_exercises_that_train_it():
    assert {o.name for o in search(SMALL, "glutes")} == {"Bodyweight Squat", "Glute Bridge"}
    assert [o.name for o in search(SMALL, "core exercises")] == ["Plank"]


def test_the_muscle_argument_filters_exactly_and_a_vague_query_matches_nothing_else():
    assert {o.name for o in search(SMALL, "", muscle="chest")} == {"Push-Up"}
    assert search(SMALL, "") == [] and search(SMALL, "the best exercise for me") == []        # never dumps the whole library
    assert search(SMALL, "something unknown") == []


def test_the_limit_is_applied_and_capped():
    many = [ex(f"k{i}", f"Squat variation {i}", ["quads"]) for i in range(20)]
    assert len(search(many, "squat", limit=3)) == 3 and len(search(many, "squat", limit=99)) == 8


def test_results_are_in_a_stable_order():
    assert [o.key for o in search(SMALL, "glutes")] == [o.key for o in search(list(reversed(SMALL)), "glutes")]


# ---------- the real library ----------

@pytest.mark.parametrize("query, expected_name", [("goblet squat", "Dumbbell Goblet Squat"), ("bulgarian split squat", "Bulgarian Split Squat"),
                                                 ("bodyweight squat", "Bodyweight Squat"), ("leg press", "Leg Press")])
def test_real_library_finds_a_named_exercise_first(query, expected_name):
    assert search(real_library(), query)[0].name == expected_name


@pytest.mark.parametrize("query, muscle", [("glutes", "glutes"), ("chest", "chest"), ("core", "abs"), ("shoulders", "shoulders"), ("hamstrings", "hamstrings")])
def test_real_library_muscle_questions_return_only_exercises_that_train_it(query, muscle):
    found = search(real_library(), query)
    assert len(found) >= 3 and all(muscle in o.muscle_groups or muscle in o.name.lower() or muscle in o.movement_pattern for o in found)


def test_real_library_nothing_invented():
    library = {o.key for o in real_library()}
    for query in ("squat", "press", "row", "plank", "stretch"):
        assert {o.key for o in search(real_library(), query)} <= library
    assert search(real_library(), "zzzz flibber") == []


# ---------- the specialist's wiring ----------

def test_the_specialist_is_read_only_with_exactly_its_two_tools_and_is_on_the_menu():
    registry = exercise_registry()
    assert registry.names() == EXERCISE_SPEC.tools == {"search_exercises", "get_exercise", "find_alternatives"} and all(t.scope == "read" for t in registry.all())
    EXERCISE_SPEC.check(registry)
    menu = default_menu()
    assert "exercises" in menu and "how to do it" in menu["exercises"].when


def test_the_prompt_forbids_inventing_exercises_diagnosing_and_building_plans():
    prompt = EXERCISE_SPEC.system_prompt.lower()
    for phrase in ("only from what the tools return", "never name, describe or invent an exercise", "fits_you", "never diagnose", "doctor or physiotherapist",
                   "never invent sets, reps or weights"):
        assert phrase in prompt


def test_the_specialist_prompt_knows_to_use_the_injury_argument_and_not_to_claim_unknown_injuries_falsely():
    prompt = EXERCISE_SPEC.system_prompt
    assert "pass it as `injury`" in prompt and "Only when fits_you is null" in prompt and "find_alternatives" in prompt and "ONLY when a tool returns an error" in prompt


# ---------- alternatives ----------

from app.calc.exercise_search import alternatives_to, find_by_name   # noqa: E402


def test_a_name_is_matched_to_a_library_exercise_or_to_nothing():
    lib = real_library()
    assert find_by_name(lib, "bench press").name.lower().count("bench") == 1 and "press" in find_by_name(lib, "bench press").name.lower()
    assert find_by_name(lib, "zzzz flibber") is None


def test_alternatives_train_the_same_primary_muscle_never_include_the_exercise_itself_and_are_stable():
    lib = real_library()
    target = find_by_name(lib, "bench press")
    found = alternatives_to(lib, target)
    assert found and all(target.muscle_groups[0] in o.muscle_groups and o.key != target.key for o in found)
    assert [o.key for o in found] == [o.key for o in alternatives_to(list(reversed(lib)), target)]


def test_the_same_movement_pattern_comes_first():
    lib = real_library()
    target = find_by_name(lib, "bench press")
    found = alternatives_to(lib, target)
    same = [o.movement_pattern == target.movement_pattern for o in found]
    assert same == sorted(same, reverse=True)                                  # all same-pattern ones, then the rest


def test_with_nothing_in_common_there_are_no_alternatives():
    lone = ex("lone", "Lone Move", ["neck"])
    assert alternatives_to([lone, ex("squat", "Squat", ["quads"])], lone) == []
