"""Allowed values used across the API, the database checks, and (later) the exercise library.

Each list is defined once here as a Literal type. tests/test_vocabulary_matches_db.py checks
that the SQL migrations allow exactly the same values.
"""

from typing import Literal, get_args

DietType = Literal["vegetarian", "non_vegetarian", "eggetarian", "vegan"]
ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
WorkoutLocation = Literal["gym", "home", "both"]
InjuryArea = Literal["shoulder", "knee", "lower_back", "neck", "wrist", "elbow", "hip", "ankle"]

# Equipment a user can have. The exercise library (Phase 5) uses the same names.
Equipment = Literal[
    "dumbbells",
    "barbell",
    "kettlebell",
    "resistance_bands",
    "pull_up_bar",
    "bench",
    "cable_machine",
    "leg_press_machine",
    "smith_machine",
    "treadmill",
    "stationary_bike",
    "jump_rope",
    "yoga_mat",
]

# How fast the user wants to go (D-042). Only picks a point inside the safety limits, never beyond them.
Pace = Literal["slow", "normal", "fast"]
# Cuisines with validated food data. A new one is added here only after its foods are loaded.
Cuisine = Literal["indian"]

PACES = get_args(Pace)
CUISINES = get_args(Cuisine)
DIET_TYPES = get_args(DietType)
EXPERIENCE_LEVELS = get_args(ExperienceLevel)
WORKOUT_LOCATIONS = get_args(WorkoutLocation)
INJURY_AREAS = get_args(InjuryArea)
EQUIPMENT = get_args(Equipment)
