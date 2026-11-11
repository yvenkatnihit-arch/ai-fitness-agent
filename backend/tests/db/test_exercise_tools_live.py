"""Step 8.2 (D-106): the exercise tools against the real database and the real library. No model is called."""

import pytest

from app.agents.context import RunContext
from app.agents.exercise_tools import GET_EXERCISE, NOT_FOUND, SEARCH_EXERCISES, UNKNOWN_FIT, KeyArgs, SearchArgs
from tests.db.test_onboarding_complete import FORMS, client, onboard, users  # noqa: F401  (shared fixtures)

pytestmark = pytest.mark.db


def search(user, **kw):
    return SEARCH_EXERCISES.run(RunContext(user), SearchArgs(**kw))


def test_a_named_exercise_is_found_with_its_details_from_the_library(client, users):
    onboard(client)
    found = search(users[0], query="goblet squat", fits_me_only=False)["exercises"]            # this user has no dumbbells, so ask for everything
    assert found[0]["name"] == "Dumbbell Goblet Squat" and found[0]["key"]
    detail = GET_EXERCISE.run(RunContext(users[0]), KeyArgs(exercise_key=found[0]["key"]))
    assert detail["name"] == "Dumbbell Goblet Squat" and detail["form_cues"] and detail["muscles"] and "movement" in detail


def test_an_exercise_that_is_not_in_the_library_is_reported_not_invented(client, users):
    onboard(client)
    assert GET_EXERCISE.run(RunContext(users[0]), KeyArgs(exercise_key="made_up_move")) == {"error": NOT_FOUND}
    assert search(users[0], query="zzzz flibber")["exercises"] == []


def test_a_muscle_search_returns_only_exercises_for_that_muscle(client, users):
    onboard(client)
    everything = search(users[0], muscle="glutes", fits_me_only=False, limit=8)["exercises"]
    assert len(everything) >= 3 and all("glutes" in e["muscles"] for e in everything)
    suitable = search(users[0], muscle="glutes", limit=8)["exercises"]                         # a beginner at home with no equipment: fewer, all fitting
    assert suitable and all("glutes" in e["muscles"] and e["fits_you"] is True for e in suitable)
    assert any(e["fits_you"] is False for e in everything)                                       # the unfiltered list has exercises this user cannot do


def test_an_injury_hides_exercises_that_would_hurt_and_the_reason_is_given_when_asked(client, users):
    onboard(client, injury_areas=["knee"])
    hidden = search(users[0], query="squat", limit=8)["exercises"]
    everything = search(users[0], query="squat", fits_me_only=False, limit=8)["exercises"]
    assert all(e["fits_you"] is True for e in hidden)
    blocked = [e for e in everything if e["fits_you"] is False]
    assert blocked and all("knee" in e["why_not"] for e in blocked)                            # the same rule the plan builder uses
    assert {e["key"] for e in blocked}.isdisjoint({e["key"] for e in hidden})


def test_the_level_and_equipment_rules_also_apply(client, users):
    onboard(client)                                                                            # beginner, trains at home with no equipment
    shown = search(users[0], query="barbell back squat", fits_me_only=False)["exercises"]
    barbell = next(e for e in shown if e["name"] == "Barbell Back Squat")
    assert barbell["fits_you"] is False and barbell["why_not"]
    assert all(e["fits_you"] for e in search(users[0], query="squat", limit=8)["exercises"])


def test_a_user_with_no_saved_training_details_gets_unknown_not_a_guess(client, users):
    found = search(users[1], query="squat")["exercises"]                                       # users[1] never onboarded
    assert found and all(e["fits_you"] is None for e in found)
    detail = GET_EXERCISE.run(RunContext(users[1]), KeyArgs(exercise_key=found[0]["key"]))
    assert detail["fits_you"] is None and detail["why_not"] == UNKNOWN_FIT


def test_no_tool_accepts_a_user_argument_or_a_muscle_that_is_not_in_the_vocabulary():
    from pydantic import ValidationError
    for bad in ({"query": "squat", "user_id": "x"}, {"muscle": "wings"}, {"limit": 99}):
        with pytest.raises(ValidationError):
            SearchArgs(**bad)
    with pytest.raises(ValidationError):
        KeyArgs(exercise_key="x", user_id="y")


def test_an_injury_named_in_the_question_filters_even_when_the_profile_has_none(client, users):
    onboard(client)                                                                                  # no injuries saved in the profile
    plain = search(users[0], muscle="shoulders", fits_me_only=False, limit=8)["exercises"]
    careful = search(users[0], muscle="shoulders", fits_me_only=False, injury="shoulder", limit=8)
    assert plain
    assert careful.get("avoiding_injury") == "shoulder" or careful["exercises"] == []
    for e in careful["exercises"]:
        assert "shoulder" not in GET_EXERCISE.run(RunContext(users[0]), KeyArgs(exercise_key=e["key"]))["not_for_people_with"]
    assert {e["key"] for e in plain} - {e["key"] for e in careful["exercises"]}                      # something that was unsafe for a shoulder was removed
    assert search(users[0], query="zzzz", injury="knee")["exercises"] == []


# ---------- alternatives (found in a real chat run: "alternative to bench press for a shoulder injury") ----------

from app.agents.exercise_tools import FIND_ALTERNATIVES, AlternativesArgs   # noqa: E402


def alternatives(user, **kw):
    return FIND_ALTERNATIVES.run(RunContext(user), AlternativesArgs(**kw))


def test_alternatives_are_other_exercises_for_the_same_muscle_that_suit_the_user(client, users):
    onboard(client)
    got = alternatives(users[0], exercise="squat")
    assert got["exercise"] and got["muscles"] and got["alternatives"] and all(a["fits_you"] is True and a["name"] != got["exercise"] for a in got["alternatives"])
    assert all(got["muscles"][0] in a["muscles"] for a in got["alternatives"])


def test_an_injury_removes_alternatives_that_would_hurt_and_explains_when_the_named_exercise_itself_is_not_suitable(client, users):
    onboard(client)
    got = alternatives(users[0], exercise="bench press", injury="shoulder")
    assert "shoulder" in got["why_not_this_one"]
    for a in got["alternatives"]:
        assert "shoulder" not in GET_EXERCISE.run(RunContext(users[0]), KeyArgs(exercise_key=a["key"]))["not_for_people_with"]
    if not got["alternatives"]:
        assert "Nothing else" in got["note"]                                                       # an honest empty answer, not "not in our library"


def test_an_unknown_exercise_is_reported_as_not_in_the_library(client, users):
    onboard(client)
    assert "No exercise like" in alternatives(users[0], exercise="zzzz flibber")["error"]


def test_a_home_beginner_asking_about_chest_exercises_gets_the_ones_that_suit_them(client, users):
    onboard(client)                                                                                  # beginner, home, no equipment
    names = {e["name"] for e in search(users[0], muscle="chest", limit=8)["exercises"]}
    assert {"Push-Up", "Knee Push-Up"} <= names                                                      # regression: these used to be cut before the filter ran
    assert search(users[0], query="squats", limit=8)["exercises"]                                      # and a plural finds the exercise
