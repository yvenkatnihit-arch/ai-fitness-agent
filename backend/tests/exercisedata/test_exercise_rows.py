import pytest

from exercisedata.load import read_validated, to_exercise_row


def csv_row(**changes) -> dict:
    base = dict(key="goblet_squat", name="Dumbbell Goblet Squat", muscle_groups="quads;glutes", equipment="dumbbells",
                location="both", difficulty="beginner", movement_pattern="squat",
                form_cues="Hold one dumbbell against your chest | Stay tall and push the floor away",
                contraindications="knee", ref_id="", reviewed_by="", note="", status="review")
    return {**base, **changes}


def test_row_becomes_db_values():
    ex = to_exercise_row(csv_row())
    assert ex.muscle_groups == ["quads", "glutes"] and ex.equipment == ["dumbbells"] and ex.contraindications == ["knee"]
    assert ex.form_cues == "Hold one dumbbell against your chest\nStay tall and push the floor away"  # one cue per line
    assert ex.source_ref is None and ex.review_status == "review"


def test_bodyweight_and_untagged_exercises_give_empty_lists():
    ex = to_exercise_row(csv_row(equipment="", contraindications="", ref_id="Dead_Bug"))
    assert ex.equipment == [] and ex.contraindications == [] and ex.source_ref == "Dead_Bug"


@pytest.mark.parametrize("change", [{"status": "blocked"}, {"form_cues": ""}, {"form_cues": "x" * 401}])
def test_rows_the_table_would_reject_fail_early_with_the_key_in_the_message(change):
    with pytest.raises(ValueError, match="goblet_squat"):
        to_exercise_row(csv_row(**change))


def test_the_real_validated_file_loads_cleanly():
    exercises = read_validated()
    assert 80 <= len(exercises) <= 130
    assert {e.review_status for e in exercises} <= {"ready", "review"}
    assert all(e.contraindications is not None and e.form_cues for e in exercises)
