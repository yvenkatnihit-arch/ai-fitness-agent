import json

import pytest

from exercisedata.find import search
from exercisedata.freedb import read_free_exercise_db
from fooddata.download import SourceError, check_json_list


def item(**changes):
    base = {"id": "Pushups", "name": "Pushups", "level": "beginner", "equipment": "body only",
            "primaryMuscles": ["chest"], "secondaryMuscles": ["shoulders", "triceps"], "category": "strength"}
    return {**base, **changes}


def write(tmp_path, items):
    path = tmp_path / "exercises.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def test_reads_fields_and_maps_expert_to_advanced(tmp_path):
    refs = read_free_exercise_db(write(tmp_path, [item(), item(id="Snatch", name="Snatch", level="expert", equipment=None)]))
    assert refs[0].primary_muscles == ("chest",) and refs[0].secondary_muscles == ("shoulders", "triceps")
    assert refs[1].level == "advanced" and refs[1].equipment is None  # missing equipment stays unknown


def test_unknown_level_and_duplicate_ids_are_refused(tmp_path):
    with pytest.raises(ValueError, match="unknown level"):
        read_free_exercise_db(write(tmp_path, [item(level="pro")]))
    with pytest.raises(ValueError, match="duplicate"):
        read_free_exercise_db(write(tmp_path, [item(), item()]))


def test_search_matches_all_words_shortest_first(tmp_path):
    refs = read_free_exercise_db(write(tmp_path, [
        item(id="a", name="Dumbbell Goblet Squat"), item(id="b", name="Goblet Squat"), item(id="c", name="Front Squat"),
    ]))
    assert [r.id for r in search(refs, "goblet squat")] == ["b", "a"]


def test_json_download_check(tmp_path):
    check_json_list(write(tmp_path, [item()]), ["id", "name"])
    with pytest.raises(SourceError, match="lack"):
        check_json_list(write(tmp_path, [{"id": 1}]), ["id", "name"])
    with pytest.raises(SourceError, match="non-empty list"):
        check_json_list(write(tmp_path, []), ["id"])
    bad = tmp_path / "page.json"
    bad.write_text("<html>rate limited</html>", encoding="utf-8")
    with pytest.raises(SourceError, match="not valid JSON"):
        check_json_list(bad, ["id"])
