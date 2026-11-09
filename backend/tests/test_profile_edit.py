"""Which fields belong to which section and what a change makes stale (pure Python)."""

import pytest

from app.calc.profile_edit import (
    ALL_FIELDS, FIELDS, MEAL_FIELDS, SCREENING_FLAGS, TARGET_FIELDS, WORKOUT_FIELDS, Effects, UnknownFields, effects, group_by_section,
)
from app.schemas.onboarding import BasicsIn, GoalIn, PreferencesIn, ScreeningIn, TrainingIn

MODELS = {"basics": BasicsIn, "goal": GoalIn, "preferences": PreferencesIn, "training": TrainingIn, "screening": ScreeningIn}


@pytest.mark.parametrize("section", list(FIELDS))
def test_every_section_lists_exactly_the_fields_of_its_onboarding_form(section):
    """If onboarding gains a question, editing must learn about it: this keeps the two in step."""
    assert set(FIELDS[section]) == set(MODELS[section].model_fields)


def test_no_field_is_in_two_sections():
    assert len(ALL_FIELDS) == len(set(ALL_FIELDS)) == sum(len(f) for f in FIELDS.values())


def test_the_six_health_flags_are_the_screening_flags():
    assert SCREENING_FLAGS == ("pregnant_or_breastfeeding", "diabetes", "heart_or_bp", "kidney", "recent_surgery_or_injury",
                               "eating_disorder_history")


def test_changes_are_grouped_by_section():
    assert group_by_section({"weight_kg": 74, "height_cm": 170, "diet_type": "vegan", "diabetes": True}) == {
        "basics": {"weight_kg": 74, "height_cm": 170}, "preferences": {"diet_type": "vegan"}, "screening": {"diabetes": True}}


@pytest.mark.parametrize("bad", ["consent_at", "onboarded_at", "id", "split_key", "focus_areas", "privacy_notice_version", "Weight_kg", ""])
def test_fields_that_cannot_be_changed_here_are_refused_by_name(bad):
    with pytest.raises(UnknownFields) as e:
        group_by_section({"weight_kg": 70, bad: "x"})
    assert e.value.fields == [bad]


def test_all_the_unknown_fields_are_reported_together():
    with pytest.raises(UnknownFields) as e:
        group_by_section({"a": 1, "weight_kg": 70, "b": 2})
    assert e.value.fields == ["a", "b"]


@pytest.mark.parametrize("changed,targets,workout,meal", [
    ([], False, False, False),
    (["display_name"], False, False, False),                           # a name changes nothing else
    (["weight_kg"], True, False, True),                                # new targets -> a new meal plan, but the workout is fine
    (["height_cm"], True, False, True),
    (["date_of_birth"], True, False, True),
    (["sex"], True, False, True),
    (["activity_level"], True, False, True),
    (["target_weight_kg"], False, False, False),                       # the target weight changes no daily number
    (["goal_type"], True, True, True),
    (["pace"], True, True, True),
    (["diet_type"], False, False, True),
    (["disliked_foods"], False, False, True),
    (["cuisine"], False, False, True),
    (["experience_level"], False, True, False),
    (["workout_location"], False, True, False),
    (["equipment"], False, True, False),
    (["days_per_week"], False, True, False),
    (["session_minutes"], False, True, False),
    (["injury_areas"], False, True, False),
    (["diabetes"], True, True, True),                                  # a health flag touches everything
    (["eating_disorder_history"], True, True, True),
    (["weight_kg", "diet_type", "equipment"], True, True, True),
])
def test_what_a_change_makes_stale(changed, targets, workout, meal):
    assert effects(changed) == Effects(targets, workout, meal)


def test_the_stale_sets_make_sense():
    assert TARGET_FIELDS <= MEAL_FIELDS                                # new targets always mean a new meal plan
    assert not (WORKOUT_FIELDS & {"diet_type", "disliked_foods", "weight_kg"})
    assert set(SCREENING_FLAGS) <= TARGET_FIELDS & WORKOUT_FIELDS & MEAL_FIELDS


def test_messages_are_plain_and_only_for_what_applies():
    assert effects([]).messages() == []
    assert effects(["diet_type"]).messages() == ["Your meal plan no longer matches your answers. Make a new one when you are ready."]
    msgs = effects(["diabetes"]).messages()
    assert len(msgs) == 3 and "targets were updated" in msgs[0] and "workout plan" in msgs[1] and "meal plan" in msgs[2]
