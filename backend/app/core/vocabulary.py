"""Allowed values used across the API, the database checks, and (later) the exercise library.

Each list is defined once here as a Literal type. tests/test_vocabulary_matches_db.py checks
that the SQL migrations allow exactly the same values.
"""

from typing import Literal, get_args

DietType = Literal["vegetarian", "non_vegetarian", "eggetarian", "vegan"]
ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
WorkoutLocation = Literal["gym", "home", "both"]
SessionMinutes = Literal[30, 45, 60, 90]
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

# What an exercise trains and how it moves (the exercise library and the workout splits both use these).
MuscleGroup = Literal[
    "chest", "back", "shoulders", "biceps", "triceps", "forearms", "abs", "glutes",
    "quads", "hamstrings", "calves", "hips", "lower_back", "traps", "neck", "full_body",
]
# Same list as the movement_pattern check in the exercises table (tests/test_vocabulary_matches_db.py).
MovementPattern = Literal[
    "squat", "hinge", "lunge", "push_horizontal", "push_vertical",
    "pull_horizontal", "pull_vertical", "carry", "core", "cardio", "mobility",
]

# Muscles a user can ask to bring up (max 2). Same list as the profiles.focus_areas check in the database.
FocusArea = Literal["chest", "back", "shoulders", "biceps", "triceps", "quads", "hamstrings", "glutes", "calves", "abs"]
MAX_FOCUS_AREAS = 2

PACES = get_args(Pace)
FOCUS_AREAS = get_args(FocusArea)
MUSCLE_GROUPS = get_args(MuscleGroup)
MOVEMENT_PATTERNS = get_args(MovementPattern)
CUISINES = get_args(Cuisine)
DIET_TYPES = get_args(DietType)
EXPERIENCE_LEVELS = get_args(ExperienceLevel)
WORKOUT_LOCATIONS = get_args(WorkoutLocation)
INJURY_AREAS = get_args(InjuryArea)
EQUIPMENT = get_args(Equipment)
