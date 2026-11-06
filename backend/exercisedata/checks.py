"""Checks for one curated exercise. Pure functions: an Exercise in, a list of Issues out.

Errors block a row from being loaded. Warnings send it to a human ('review').
"""

import re
from collections import Counter

from app.core.vocabulary import EQUIPMENT, EXPERIENCE_LEVELS, INJURY_AREAS, WORKOUT_LOCATIONS
from exercisedata import rules
from exercisedata.freedb import ExerciseRef
from exercisedata.records import Exercise
from fooddata.checks import Issue

KEY_FORMAT = re.compile(r"^[a-z][a-z0-9_]{1,59}$")


def error(check: str, message: str) -> Issue:
    return Issue(check, "error", message)


def warning(check: str, message: str) -> Issue:
    return Issue(check, "warning", message)


def check_vocabulary(ex: Exercise) -> list[Issue]:
    issues = []
    if not KEY_FORMAT.match(ex.key):
        issues.append(error("vocabulary", f"key {ex.key!r} must be lower_snake_case"))
    if not 1 <= len(ex.name) <= 80:
        issues.append(error("vocabulary", "name must be 1-80 characters"))
    if not ex.muscle_groups:
        issues.append(error("vocabulary", "at least one muscle group is needed"))
    for label, values, allowed in (
        ("muscle group", ex.muscle_groups, rules.MUSCLE_GROUPS),
        ("equipment", ex.equipment, EQUIPMENT),
        ("injury tag", ex.contraindications, INJURY_AREAS),
    ):
        issues += [error("vocabulary", f"unknown {label} {v!r}") for v in values if v not in allowed]
        issues += [error("vocabulary", f"{label} {v!r} listed twice") for v, n in Counter(values).items() if n > 1]
    for label, value, allowed in (
        ("location", ex.location, WORKOUT_LOCATIONS),
        ("difficulty", ex.difficulty, EXPERIENCE_LEVELS),
        ("movement pattern", ex.movement_pattern, rules.MOVEMENT_PATTERNS),
    ):
        if value not in allowed:
            issues.append(error("vocabulary", f"unknown {label} {value!r}"))
    return issues


def check_cues(ex: Exercise) -> list[Issue]:
    issues = []
    if not rules.CUES_MIN <= len(ex.cues) <= rules.CUES_MAX:
        issues.append(error("cues", f"needs {rules.CUES_MIN}-{rules.CUES_MAX} form cues, has {len(ex.cues)}"))
    for cue in ex.cues:
        if not rules.CUE_CHARS_MIN <= len(cue) <= rules.CUE_CHARS_MAX:
            issues.append(error("cues", f"cue is {len(cue)} characters (allowed {rules.CUE_CHARS_MIN}-{rules.CUE_CHARS_MAX}): {cue[:40]!r}"))
    if len("\n".join(ex.cues)) > rules.CUES_TOTAL_MAX:
        issues.append(error("cues", f"cues total more than {rules.CUES_TOTAL_MAX} characters (database limit)"))
    return issues


def check_location(ex: Exercise) -> list[Issue]:
    needs_gym = [e for e in ex.equipment if e in rules.GYM_ONLY_EQUIPMENT]
    if needs_gym and ex.location != "gym":
        return [error("location", f"{', '.join(needs_gym)} is gym equipment, so location must be 'gym' (is {ex.location!r})")]
    return []


def required_injury_tags(ex: Exercise) -> dict[str, str]:
    """Tag -> reason, for every tag this exercise MUST carry."""
    needed = {tag: f"{ex.movement_pattern} pattern" for tag in rules.PATTERN_TAGS.get(ex.movement_pattern, ())}
    name = ex.name.lower()
    for pattern, tags, why in rules.NAME_TAGS:
        if pattern.search(name):
            for tag in tags:
                needed.setdefault(tag, why)
    return needed


def check_injury_tags(ex: Exercise) -> list[Issue]:
    return [
        error("injury_tags", f"missing injury tag {tag!r} ({why})")
        for tag, why in required_injury_tags(ex).items() if tag not in ex.contraindications
    ]


def check_reference(ex: Exercise, ref: ExerciseRef | None) -> list[Issue]:
    """Compare with the Free Exercise DB entry we cite. Disagreements are warnings for a human."""
    if not ex.ref_id:
        return []  # nothing to compare with; build.py lists these in the report as "not cross-checked"
    if ref is None:
        return [error("reference", f"Free Exercise DB id {ex.ref_id!r} not found")]
    issues = []
    if ex.difficulty != ref.level:
        issues.append(warning("reference", f"difficulty is {ex.difficulty}, Free Exercise DB says {ref.level}"))
    theirs = set(ref.primary_muscles) | set(ref.secondary_muscles)
    their_groups = {rules.FREE_DB_MUSCLES[m] for m in theirs if m in rules.FREE_DB_MUSCLES}
    main = ex.muscle_groups[0] if ex.muscle_groups else ""
    if main not in ("full_body", "") and their_groups and main not in their_groups:
        issues.append(warning("reference", f"main muscle {main} is not among theirs ({', '.join(sorted(their_groups))})"))
    mapped = [e for e in ex.equipment if e in rules.FREE_DB_EQUIPMENT]
    if mapped:
        agreeing = set().union(*(rules.FREE_DB_EQUIPMENT[e] for e in mapped)) | {None, "other"}
        if ref.equipment not in agreeing:
            issues.append(warning("reference", f"equipment {', '.join(mapped)} vs theirs {ref.equipment!r}"))
    elif not ex.equipment and ref.equipment not in rules.FREE_DB_NO_EQUIPMENT:
        issues.append(warning("reference", f"we list no equipment, theirs says {ref.equipment!r}"))
    return issues


def check_exercise(ex: Exercise, ref: ExerciseRef | None) -> list[Issue]:
    return [*check_vocabulary(ex), *check_cues(ex), *check_location(ex), *check_injury_tags(ex), *check_reference(ex, ref)]


def check_library(exercises: list[Exercise]) -> list[Issue]:
    """Checks across rows: unique keys and names."""
    issues = []
    for label, values in (("key", [e.key for e in exercises]), ("name", [e.name.lower() for e in exercises])):
        issues += [error("duplicate", f"{label} {v!r} appears {n} times") for v, n in Counter(values).items() if n > 1]
    return issues
