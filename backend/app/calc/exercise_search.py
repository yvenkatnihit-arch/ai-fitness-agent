"""Searching the exercise library by words and muscle (Step 8.2, D-106). Pure Python: no database, no model.

Used by the exercise specialist in chat. It only ranks what is in the library; it can never produce an exercise that is not there."""

import re
from collections.abc import Sequence

from app.calc.exercise_filter import LEVEL_ORDER, ExerciseOption

STOP_WORDS = frozenset({"the", "and", "for", "with", "how", "what", "can", "you", "do", "does", "any", "that", "this", "exercise", "exercises", "workout",
                        "work", "works", "train", "trains", "training", "target", "tone", "build", "best", "good", "some", "show", "give", "me", "my", "to", "of", "a", "an", "in", "on", "at", "home", "gym"})
# Everyday words for the muscle names stored in the library.
SYNONYMS = {"core": "abs", "abdominals": "abs", "abdominal": "abs", "stomach": "abs", "belly": "abs", "bum": "glutes", "butt": "glutes", "glute": "glutes",
            "pecs": "chest", "lats": "back", "delts": "shoulders", "shoulder": "shoulders", "quad": "quads", "thighs": "quads", "legs": "quads",
            "hamstring": "hamstrings", "calf": "calves", "bicep": "biceps", "tricep": "triceps", "arms": "biceps", "trap": "traps", "hip": "hips"}
MAX_RESULTS = 8


def words(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z]+", text.lower()):
        w = SYNONYMS.get(w, w)
        if len(w) >= 3 and w not in STOP_WORDS:
            out.append(w)
    return out


def score(option: ExerciseOption, query_words: Sequence[str]) -> int:
    name = option.name.lower()
    compact = re.sub(r"[^a-z]", "", name)                  # "push-up" -> "pushup", so a query written either way finds it
    muscles = " ".join(option.muscle_groups).replace("_", " ")
    other = f"{' '.join(option.equipment)} {option.movement_pattern.replace('_', ' ')}".lower()
    total = 0
    for w in query_words:
        forms = (w, w[:-1]) if w.endswith("s") and len(w) > 3 else (w,)      # "squats" finds "Squat", "lunges" finds "Lunge"
        if any(f in name or f in compact for f in forms):
            total += 3
        if any(f in muscles for f in forms):
            total += 2
        if any(f in other for f in forms):
            total += 1
    return total


def search(options: Sequence[ExerciseOption], query: str, muscle: str | None = None, limit: int | None = 5) -> list[ExerciseOption]:
    """The best matches first (on equal scores the easier exercise wins, then the shorter name: "Bodyweight Squat" before "Jump Squat"). A `muscle` keeps only exercises that train it. A query with no usable words and no muscle matches nothing,
    so a vague question never dumps the whole library."""
    cap = None if limit is None else max(1, min(limit, MAX_RESULTS))        # limit=None: every match (the caller filters, THEN cuts)
    pool = [o for o in options if muscle is None or muscle in o.muscle_groups]
    query_words = words(query)
    if not query_words:
        return sorted(pool, key=lambda o: o.name)[:cap] if muscle else []
    ranked = [(score(o, query_words), o) for o in pool]
    return [o for s, o in sorted(ranked, key=lambda pair: (-pair[0], LEVEL_ORDER[pair[1].difficulty], len(pair[1].name), pair[1].name)) if s > 0][:cap]


def find_by_name(options: Sequence[ExerciseOption], name: str) -> ExerciseOption | None:
    """The library exercise that best matches a name, or None (a name no exercise matches at all is NOT in our library)."""
    found = search(options, name, None, 1)
    return found[0] if found else None


def alternatives_to(options: Sequence[ExerciseOption], target: ExerciseOption) -> list[ExerciseOption]:
    """Other exercises that train the same main muscles, best first: the same movement pattern first, then the most muscles in common,
    then by name (stable). The caller still applies the user's own limits (injury, level, place, equipment)."""
    main = set(target.muscle_groups[:2])
    ranked = []
    for o in options:
        if o.key == target.key:
            continue
        shared = len(main & set(o.muscle_groups))
        if shared == 0 or target.muscle_groups[0] not in o.muscle_groups:
            continue                                   # it must train the target's PRIMARY muscle
        ranked.append(((o.movement_pattern == target.movement_pattern, shared), o))
    return [o for _, o in sorted(ranked, key=lambda pair: (not pair[0][0], -pair[0][1], pair[1].name))]
