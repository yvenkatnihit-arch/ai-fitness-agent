"""Workout splits: which ones fit a user, and what each training day contains (Step 6.2, D-042).

A *split* is how the week's training is divided: full body each time, push/pull/legs, upper/lower...
Everything here is plain code. The model never invents a split: it can only explain these (the brief:
"the LLM never invents exercises", and the same goes for the structure of the week).

Each training day lists the muscles it trains and the movement patterns the plan generator will pick
exercises for (patterns and muscles are the exercise library's own vocabulary).
"""

from dataclasses import dataclass
from typing import Literal

from app.calc.targets import Goal
from app.core.vocabulary import MOVEMENT_PATTERNS, MUSCLE_GROUPS, ExperienceLevel

Fit = Literal["best", "good", "possible"]


@dataclass(frozen=True)
class SplitDay:
    label: str
    muscles: tuple[str, ...]
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class Split:
    key: str                       # stable id, saved when the user picks one: "upper_lower_4"
    name: str
    summary: str
    days: tuple[SplitDay, ...]     # the training days, in order
    muscle_frequency: int          # how many times a week each main muscle is trained
    level_fit: tuple[int, int, int]  # 0 = too demanding, 1 = works, 2 = well suited: (beginner, intermediate, advanced)

    @property
    def training_days(self) -> int:
        return len(self.days)


# --- Building blocks (each day is a list of muscles and movement patterns) ---

def _day(label: str, muscles: tuple[str, ...], patterns: tuple[str, ...]) -> SplitDay:
    return SplitDay(label, muscles, patterns)


FULL = _day("Full body", ("quads", "glutes", "hamstrings", "chest", "back", "shoulders", "abs"),
            ("squat", "hinge", "push_horizontal", "pull_horizontal", "push_vertical", "core"))
PUSH = _day("Push", ("chest", "shoulders", "triceps"), ("push_horizontal", "push_vertical"))
PULL = _day("Pull", ("back", "biceps", "traps"), ("pull_vertical", "pull_horizontal"))
LEGS = _day("Legs", ("quads", "hamstrings", "glutes", "calves"), ("squat", "lunge", "hinge", "core"))
UPPER = _day("Upper body", ("chest", "back", "shoulders", "biceps", "triceps"),
             ("push_horizontal", "pull_horizontal", "push_vertical", "pull_vertical"))
LOWER = _day("Lower body", ("quads", "hamstrings", "glutes", "calves", "abs"), ("squat", "hinge", "lunge", "core"))
CHEST_BACK = _day("Chest and back", ("chest", "back"), ("push_horizontal", "pull_horizontal", "pull_vertical"))
SHOULDERS_ARMS = _day("Shoulders and arms", ("shoulders", "biceps", "triceps"),
                      ("push_vertical", "pull_horizontal", "push_horizontal"))
CHEST = _day("Chest", ("chest", "triceps"), ("push_horizontal",))
BACK = _day("Back", ("back", "biceps"), ("pull_vertical", "pull_horizontal"))
SHOULDERS = _day("Shoulders", ("shoulders", "traps"), ("push_vertical", "pull_horizontal"))
ARMS = _day("Arms", ("biceps", "triceps", "forearms"), ("pull_horizontal", "push_horizontal"))
LEGS_CORE = _day("Legs and core", ("quads", "hamstrings", "glutes", "calves", "abs"),
                 ("squat", "lunge", "hinge", "core"))


def _full_body(days: int, level_fit: tuple[int, int, int]) -> Split:
    letters = "ABCD"
    return Split(
        key=f"full_body_{days}", name="Full body",
        summary="Every session trains your whole body. Simple, forgiving if you miss a day, and the best way to learn the lifts.",
        days=tuple(SplitDay(f"Full body {letters[i]}" if days > 1 else "Full body", FULL.muscles, FULL.patterns)
                   for i in range(days)),
        muscle_frequency=days, level_fit=level_fit,
    )


CATALOGUE: tuple[Split, ...] = (
    _full_body(1, (2, 1, 1)),
    _full_body(2, (2, 1, 1)),
    _full_body(3, (2, 1, 1)),
    _full_body(4, (1, 1, 1)),
    Split("ppl_3", "Push / Pull / Legs",
          "Three sessions: pushing muscles, pulling muscles, then legs. Each muscle is trained once a week.",
          (PUSH, PULL, LEGS), 1, (1, 2, 1)),
    Split("upper_lower_4", "Upper / Lower",
          "Four sessions: upper body, lower body, then again. Every muscle twice a week with time to recover.",
          (UPPER, LOWER, UPPER, LOWER), 2, (1, 2, 2)),
    Split("upper_lower_ppl_5", "Upper / Lower + Push / Pull / Legs",
          "Five sessions that mix both styles. Most muscles are trained about twice a week.",
          (UPPER, LOWER, PUSH, PULL, LEGS), 2, (0, 2, 2)),
    Split("bro_5", "Body-part split",
          "One main muscle group per day: chest, back, shoulders, arms, legs. Long sessions, each muscle once a week.",
          (CHEST, BACK, SHOULDERS, ARMS, LEGS_CORE), 1, (0, 1, 1)),
    Split("ppl_6", "Push / Pull / Legs, twice a week",
          "Six sessions: push, pull, legs, then again. A lot of volume; every muscle twice a week.",
          (PUSH, PULL, LEGS, PUSH, PULL, LEGS), 2, (0, 1, 2)),
    Split("arnold_6", "Arnold split",
          "Six sessions: chest and back, shoulders and arms, legs, then again. A classic high-volume bodybuilding plan.",
          (CHEST_BACK, SHOULDERS_ARMS, LEGS_CORE, CHEST_BACK, SHOULDERS_ARMS, LEGS_CORE), 2, (0, 1, 2)),
)
BY_KEY = {split.key: split for split in CATALOGUE}
LEVEL_INDEX = {"beginner": 0, "intermediate": 1, "advanced": 2}


@dataclass(frozen=True)
class Recommendation:
    split: Split
    fit: Fit
    score: int                       # 0-3: level suitability (0-2) + 1 if each muscle is trained twice a week or more
    recovery_days: int               # easy days (walking, stretching) on top of the training days: 1 when asked for 7
    reasons: tuple[str, ...]
    cautions: tuple[str, ...]


def _training_days_for(days_per_week: int) -> int:
    """Seven days a week still means at most six hard sessions; the seventh is an easy recovery day."""
    return min(days_per_week, 6)


def recommend_splits(days_per_week: int, level: ExperienceLevel, goal: Goal) -> list[Recommendation]:
    """Every split that fits the number of days, best first. Empty never happens for 1-7 days."""
    if isinstance(days_per_week, bool) or not isinstance(days_per_week, int) or not 1 <= days_per_week <= 7:
        raise ValueError(f"days_per_week must be a whole number from 1 to 7, got {days_per_week!r}")
    if level not in LEVEL_INDEX:
        raise ValueError(f"level must be one of {list(LEVEL_INDEX)}, got {level!r}")

    training = _training_days_for(days_per_week)
    recovery = days_per_week - training
    scored: list[tuple[int, int, Split]] = []
    for order, split in enumerate(CATALOGUE):
        if split.training_days != training:
            continue
        fit = split.level_fit[LEVEL_INDEX[level]]
        score = fit + (1 if split.muscle_frequency >= 2 else 0)
        scored.append((score, order, split))
    scored.sort(key=lambda item: (-item[0], item[1]))
    top = scored[0][0]

    result = []
    for score, _, split in scored:
        label: Fit = "best" if score == top and score >= 2 else "good" if score >= 2 else "possible"
        result.append(Recommendation(
            split=split, fit=label, score=score, recovery_days=recovery,
            reasons=_reasons(split, days_per_week, level, recovery),
            cautions=_cautions(split, level, goal, recovery),
        ))
    return result


def _reasons(split: Split, days_per_week: int, level: str, recovery: int) -> tuple[str, ...]:
    reasons = [f"{split.training_days} training {'day' if split.training_days == 1 else 'days'} a week, as you asked"
               if not recovery else f"{split.training_days} hard sessions plus {recovery} easy recovery day for your {days_per_week} days"]
    freq = split.muscle_frequency
    reasons.append("Trains each muscle once a week" if freq == 1 else f"Trains each muscle about {freq} times a week")
    fit = split.level_fit[LEVEL_INDEX[level]]
    if fit == 2:
        reasons.append(f"A good match for {level} lifters")
    elif fit == 1:
        reasons.append(f"Works for {level} lifters")
    return tuple(reasons)


def _cautions(split: Split, level: str, goal: str, recovery: int) -> tuple[str, ...]:
    cautions = []
    if split.level_fit[LEVEL_INDEX[level]] == 0:
        cautions.append("Asks for more training experience than you have so far; it is easier to start with fewer, shorter sessions")
    if split.muscle_frequency == 1 and split.training_days > 1 and goal in ("muscle_gain", "weight_gain", "recomp"):
        cautions.append("Each muscle gets one session a week, which usually builds muscle more slowly")
    if split.training_days == 6:
        cautions.append("Six hard days a week leaves little room for poor sleep or missed meals")
    if recovery:
        cautions.append("Use the extra day for walking or stretching, not hard training")
    return tuple(cautions)


def fits_days(split_key: str, days_per_week: int) -> bool:
    """Is this split one of the choices for this number of days? (7 days = a six-day split plus a recovery day.)"""
    return split_key in BY_KEY and BY_KEY[split_key].training_days == _training_days_for(days_per_week)


def split_by_key(key: str) -> Split:
    if key not in BY_KEY:
        raise ValueError(f"unknown split {key!r}")
    return BY_KEY[key]


def check_catalogue() -> list[str]:
    """Problems in the catalogue itself (used by a test): unknown muscles or patterns, repeated keys."""
    problems = []
    if len(BY_KEY) != len(CATALOGUE):
        problems.append("repeated split key")
    for split in CATALOGUE:
        for day in split.days:
            problems += [f"{split.key}/{day.label}: unknown muscle {m}" for m in day.muscles if m not in MUSCLE_GROUPS]
            problems += [f"{split.key}/{day.label}: unknown pattern {p}" for p in day.patterns if p not in MOVEMENT_PATTERNS]
    return problems
