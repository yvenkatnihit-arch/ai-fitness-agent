from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.core.time import india_today
from app.schemas.onboarding import BasicsIn, ConsentIn, GoalIn, PreferencesIn, ScreeningIn, TrainingIn


def years_ago(years: int, plus_days: int = 0) -> date:
    today = india_today()
    try:
        return today.replace(year=today.year - years) + timedelta(days=plus_days)
    except ValueError:  # today is 29 Feb and that year has none
        return date(today.year - years, 3, 1) + timedelta(days=plus_days)


BASICS = {
    "date_of_birth": "1995-08-20",
    "sex": "female",
    "height_cm": 162.5,
    "weight_kg": 58.0,
    "activity_level": "light",
}


def basics(**changes):
    return BasicsIn.model_validate({**BASICS, **changes})


# --- Basics ---

def test_valid_basics():
    b = basics(display_name="  Kruthi  ")
    assert b.display_name == "Kruthi"  # trimmed
    assert b.height_cm == 162.5


def test_whole_numbers_are_fine_for_height_and_weight():
    assert basics(height_cm=170, weight_kg=70).weight_kg == 70


def test_exactly_18_today_is_allowed():
    assert basics(date_of_birth=years_ago(18).isoformat())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("date_of_birth", None),               # filled in by the param below
        ("height_cm", 1.62),                   # metres instead of cm
        ("height_cm", 250),
        ("weight_kg", 580),                    # extra digit
        ("weight_kg", True),                   # bool is not a number here
        ("height_cm", "162"),                  # text instead of a number
        ("sex", "F"),
        ("activity_level", "very active"),
    ],
)
def test_bad_basics_are_refused(field, value):
    if field == "date_of_birth":
        value = years_ago(18, plus_days=1).isoformat()  # turns 18 tomorrow
    with pytest.raises(ValidationError):
        basics(**{field: value})


def test_future_birth_date_is_refused():
    with pytest.raises(ValidationError, match="future"):
        basics(date_of_birth=(india_today() + timedelta(days=1)).isoformat())


def test_over_100_is_refused():
    with pytest.raises(ValidationError):
        basics(date_of_birth=years_ago(101).isoformat())


def test_unknown_fields_are_refused():
    # Nobody can slip extra fields like user_id or onboarded_at into a form.
    with pytest.raises(ValidationError):
        basics(user_id="00000000-0000-0000-0000-000000000000")


# --- Consent ---

def test_consent_must_be_exactly_true():
    assert ConsentIn(health_data_consent=True, privacy_notice_version="2026-11")
    for bad in (False, "true", 1):
        with pytest.raises(ValidationError):
            ConsentIn(health_data_consent=bad, privacy_notice_version="2026-11")


# --- Goal ---

def test_goal():
    assert GoalIn(goal_type="fat_loss", target_weight_kg=55).target_weight_kg == 55
    assert GoalIn(goal_type="general_fitness").target_weight_kg is None
    with pytest.raises(ValidationError):
        GoalIn(goal_type="bulk")
    with pytest.raises(ValidationError):
        GoalIn(goal_type="fat_loss", target_weight_kg=20)


# --- Preferences ---

def test_disliked_foods_are_trimmed_and_deduplicated():
    p = PreferencesIn(diet_type="vegetarian", disliked_foods=["  Brinjal ", "brinjal", "Karela"])
    assert p.disliked_foods == ["Brinjal", "Karela"]


@pytest.mark.parametrize("foods", [[""], ["   "], ["x" * 61], [f"food {i}" for i in range(31)]])
def test_bad_disliked_foods_are_refused(foods):
    with pytest.raises(ValidationError):
        PreferencesIn(diet_type="vegan", disliked_foods=foods)


def test_unknown_diet_is_refused():
    with pytest.raises(ValidationError):
        PreferencesIn(diet_type="pescatarian")


# --- Training ---

def test_training():
    t = TrainingIn(experience_level="beginner", workout_location="home",
                   equipment=["dumbbells", "yoga_mat", "dumbbells"], days_per_week=3)
    assert t.equipment == ["dumbbells", "yoga_mat"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("equipment", ["rowing_machine"]), ("days_per_week", 0), ("days_per_week", 8), ("workout_location", "park")],
)
def test_bad_training_is_refused(field, value):
    data = {"experience_level": "beginner", "workout_location": "gym", "equipment": [], "days_per_week": 4}
    with pytest.raises(ValidationError):
        TrainingIn.model_validate({**data, field: value})


# --- Screening ---

SCREENING = {
    "pregnant_or_breastfeeding": False,
    "diabetes": True,
    "heart_or_bp": False,
    "kidney": True,
    "recent_surgery_or_injury": False,
    "eating_disorder_history": False,
    "injury_areas": ["knee", "knee", "lower_back"],
}


def test_screening_flags():
    s = ScreeningIn.model_validate(SCREENING)
    assert s.flags() == {"diabetes", "kidney"}
    assert s.injury_areas == ["knee", "lower_back"]


def test_every_screening_question_must_be_answered():
    missing = {k: v for k, v in SCREENING.items() if k != "kidney"}
    with pytest.raises(ValidationError):
        ScreeningIn.model_validate(missing)


@pytest.mark.parametrize("vague", ["yes", "no", 1, 0, None])
def test_screening_answers_must_be_true_or_false(vague):
    with pytest.raises(ValidationError):
        ScreeningIn.model_validate({**SCREENING, "diabetes": vague})


def test_unknown_injury_area_is_refused():
    with pytest.raises(ValidationError):
        ScreeningIn.model_validate({**SCREENING, "injury_areas": ["toe"]})
