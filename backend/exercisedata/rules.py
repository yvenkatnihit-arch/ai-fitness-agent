"""The judgement calls behind the exercise checks, in one place so they can be reviewed (D-041).

Nothing here is medical advice. The injury rules only say "an exercise like this MUST carry at least
these tags"; they make us err on the side of hiding an exercise from a user who reported that body area.
"""

import re

# Muscle groups in OUR words (the exercises table stores free text, so the list lives here).
MUSCLE_GROUPS = (
    "chest", "back", "shoulders", "biceps", "triceps", "forearms", "abs", "glutes",
    "quads", "hamstrings", "calves", "hips", "lower_back", "traps", "neck", "full_body",
)

# Same list as the movement_pattern check in the exercises table.
MOVEMENT_PATTERNS = (
    "squat", "hinge", "lunge", "push_horizontal", "push_vertical",
    "pull_horizontal", "pull_vertical", "carry", "core", "cardio", "mobility",
)

# Free Exercise DB muscle -> our muscle group (cross-check only).
FREE_DB_MUSCLES = {
    "abdominals": "abs", "abductors": "hips", "adductors": "hips", "biceps": "biceps", "calves": "calves",
    "chest": "chest", "forearms": "forearms", "glutes": "glutes", "hamstrings": "hamstrings", "lats": "back",
    "lower back": "lower_back", "middle back": "back", "neck": "neck", "quadriceps": "quads",
    "shoulders": "shoulders", "traps": "traps", "triceps": "triceps",
}

# Our equipment -> the Free Exercise DB words that agree with it. Equipment with no entry here
# (pull_up_bar, bench, yoga_mat, jump_rope) is not cross-checked: the dataset has no matching word.
FREE_DB_EQUIPMENT = {
    "dumbbells": {"dumbbell"}, "barbell": {"barbell"}, "kettlebell": {"kettlebells"},
    "resistance_bands": {"bands"}, "cable_machine": {"cable"},
    "leg_press_machine": {"machine"}, "smith_machine": {"machine"},
    "treadmill": {"machine"}, "stationary_bike": {"machine"},
}
FREE_DB_NO_EQUIPMENT = {"body only", "foam roll", "other", None}  # words that agree with "no equipment"

# These need a gym, so the exercise's location must be 'gym'.
GYM_ONLY_EQUIPMENT = ("cable_machine", "leg_press_machine", "smith_machine")

CUES_MIN, CUES_MAX = 2, 4          # brief: 2-4 short lines of text
CUE_CHARS_MIN, CUE_CHARS_MAX = 8, 110
CUES_TOTAL_MAX = 400               # the exercises.form_cues column limit (cues are joined with newlines)

# Minimum injury tags by movement pattern: (pattern, tags).
PATTERN_TAGS: dict[str, tuple[str, ...]] = {
    "squat": ("knee",),
    "lunge": ("knee",),
    "hinge": ("lower_back",),
    "push_horizontal": ("shoulder",),
    "push_vertical": ("shoulder",),
    "pull_vertical": ("shoulder", "elbow"),
    "carry": ("lower_back",),
}

# Minimum injury tags by name: (regex on the lower-case name, tags, why). Applies to every pattern.
NAME_TAGS: tuple[tuple[re.Pattern, tuple[str, ...], str], ...] = tuple(
    (re.compile(pattern), tags, why) for pattern, tags, why in (
        (r"\b(jump|jumps|jumping|burpee|burpees|skater|hop|sprint|run|running|jacks|high knees)\b",
         ("knee", "ankle"), "jumping or running lands on the knees and ankles"),
        (r"\b(push-?ups?|plank|planks|mountain climbers?)\b", ("wrist",), "load through the wrists"),
        (r"\bdips?\b", ("shoulder", "elbow"), "dips stress the front of the shoulder and the elbows"),
        (r"\b(crunch|crunches|sit-?ups?)\b", ("neck",), "neck flexion"),
        (r"\btwists?\b", ("lower_back",), "spinal rotation"),
        (r"(?<!leg )(?<!hamstring )\bcurls?\b", ("elbow",), "elbow flexion under load"),
        (r"\b(triceps|skull|pushdown|pullover)\b", ("elbow",), "elbow extension under load"),
        (r"\bpullover\b", ("shoulder",), "overhead arc"),
        (r"\b(barbell|front|smith)\b.*\bsquat\b|\bsquat\b.*\b(barbell|front|smith)\b|\bleg press\b",
         ("lower_back",), "heavy squat loading on the spine"),
        (r"\b(bent-over|bent over|superman|good morning|swing)\b", ("lower_back",), "loaded or arched back"),
        (r"\bwall sit\b", ("knee",), "long static knee load"),
        (r"\b(hanging|pull-?ups?|chin-?ups?)\b", ("shoulder",), "hanging from the arms"),
        (r"\bshrugs?\b", ("neck",), "heavy load through the neck and traps"),
    )
)
