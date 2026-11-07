"""Which exercises may a split day use, and is a pick for that day acceptable? (Step 6.6b). Plain code.

The model only ever CHOOSES from `day_candidates`. Everything it returns is checked here, and a day it
gets wrong falls back to `fallback_picks`, so an invented or unsafe exercise can never reach a plan.
"""

from collections import Counter
from collections.abc import Collection, Sequence

from app.calc.exercise_filter import ExerciseOption
from app.calc.routine import exercise_kind
from app.calc.splits import SplitDay

EXERCISES_PER_DAY = {"beginner": 4, "intermediate": 5, "advanced": 6}
MIN_DAY_EXERCISES = 3        # a training day with fewer possible exercises than this is not a workout
MIN_PATTERN_CAP = 3          # at most this many picks from one movement pattern (more if the day has few patterns)
KIND_ORDER = {"compound": 0, "isolation": 1, "core": 2, "timed": 2}
LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def day_candidates(day: SplitDay, allowed: Sequence[ExerciseOption]) -> list[ExerciseOption]:
    """From the already-filtered exercises (injuries, level, place, equipment): those that fit this day.

    An exercise fits when its movement pattern is one of the day's patterns AND it trains at least one of the
    day's muscles. Blocked exercises are never used. Stable order, so the same inputs give the same list.
    """
    muscles = set(day.muscles)
    fits = [
        o for o in allowed
        if o.review_status != "blocked" and o.movement_pattern in day.patterns and muscles & set(o.muscle_groups)
    ]
    return sorted(fits, key=lambda o: (LEVEL_ORDER[o.difficulty], o.name))


def wanted_count(level: str, candidates: Sequence[ExerciseOption], per_day: int | None = None) -> int:
    """How many exercises the day should have: `per_day` (from the session length) or by level, and never more than exist."""
    return min(per_day if per_day is not None else EXERCISES_PER_DAY[level], len(candidates))


def pattern_cap(wanted: int, patterns_available: int) -> int:
    """A day with one pattern (a chest day) must be allowed more than three of it."""
    return max(MIN_PATTERN_CAP, -(-wanted // max(patterns_available, 1)))


def validate_picks(keys: object, candidates: Sequence[ExerciseOption], wanted: int) -> list[str]:
    """Everything wrong with these picks, in plain words. An empty list means the picks are acceptable."""
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        return ["the exercises must be a list of keys"]
    by_key = {o.key: o for o in candidates}
    problems: list[str] = []
    unknown = [k for k in keys if k not in by_key]
    if unknown:
        problems.append(f"not in the allowed list: {', '.join(sorted(set(unknown))[:5])}")
    repeated = sorted(k for k, n in Counter(keys).items() if n > 1)
    if repeated:
        problems.append(f"repeated: {', '.join(repeated[:5])}")
    if len(keys) != wanted:
        problems.append(f"need exactly {wanted} exercises, got {len(keys)}")
    chosen = [by_key[k] for k in dict.fromkeys(keys) if k in by_key]
    patterns_available = len({o.movement_pattern for o in candidates})
    per_pattern = Counter(o.movement_pattern for o in chosen)
    cap = pattern_cap(wanted, patterns_available)
    too_many = [p for p, n in per_pattern.items() if n > cap]
    if too_many:
        problems.append(f"too many from one movement ({', '.join(too_many)}); at most {cap}")
    need_variety = min(wanted, patterns_available)
    if not unknown and len(per_pattern) < need_variety:
        problems.append(f"cover at least {need_variety} different movements, got {len(per_pattern)}")
    return problems


def order_picks(keys: Sequence[str], candidates: Sequence[ExerciseOption]) -> list[str]:
    """Big lifts first, then single-muscle work, then core. The model's own order is kept within each group."""
    by_key = {o.key: o for o in candidates}

    def rank(key: str) -> int:
        o = by_key[key]
        return KIND_ORDER.get(exercise_kind(o.movement_pattern, o.muscle_groups, o.name) or "core", 2)

    return sorted(keys, key=rank)   # sorted() is stable


def fallback_picks(candidates: Sequence[ExerciseOption], wanted: int, used: Sequence[str] = (),
                   focus: Collection[str] = ()) -> list[str]:
    """A safe, boring pick made by code: round-robin over the day's movements, big lifts first, easiest first.

    `used` are exercises already placed on other days; they are chosen last, so the week has variety.
    Exercises that train a `focus` muscle come first within their movement.
    """
    def kind_rank(o: ExerciseOption) -> int:
        return KIND_ORDER.get(exercise_kind(o.movement_pattern, o.muscle_groups, o.name) or "core", 2)

    ordered_patterns = list(dict.fromkeys(o.movement_pattern for o in candidates))
    queues = {
        p: sorted((o for o in candidates if o.movement_pattern == p),
                  key=lambda o: (o.key in used, not (set(focus) & set(o.muscle_groups)), kind_rank(o),
                         LEVEL_ORDER[o.difficulty], o.name))
        for p in ordered_patterns
    }
    cap = pattern_cap(wanted, len(ordered_patterns))
    picked: list[ExerciseOption] = []
    taken = Counter[str]()
    while len(picked) < wanted:
        progressed = False
        for p in ordered_patterns:
            if len(picked) < wanted and queues[p] and taken[p] < cap:
                picked.append(queues[p].pop(0))
                taken[p] += 1
                progressed = True
        if not progressed:
            break
    return order_picks([o.key for o in picked], candidates)
