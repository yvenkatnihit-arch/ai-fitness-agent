"""Step 7.9a (D-087): generated workout plans are trimmed to the weekly hard-set cap, in code."""

from datetime import date

import pytest

from app.calc.day_picks import MIN_DAY_EXERCISES
from app.calc.exercise_filter import ExerciseOption
from app.calc.routine import MIN_SETS
from app.calc.splits import split_by_key
from app.calc.weekly_cap import enforce_weekly_cap
from app.calc.workout_edit import weekly_sets
from app.calc.workout_plan import DayPick, build_payload, validate_payload
from app.safety.safety_config import MAX_WEEKLY_SETS_PER_MUSCLE as CAP


def ex(key, sets, position):
    return {"exercise_key": key, "name": key, "position": position, "sets": sets, "reps_min": 8, "reps_max": 10, "rest_sec": 90, "note": None}


def day(*exs, rest=False):
    return {"day_of_week": 1, "focus": "Rest" if rest else "Day", "is_rest": rest, "minutes": None if rest else 40, "exercises": list(exs)}


def sets_of(days, main):
    return sum(e["sets"] for d in days for e in d["exercises"] if main[e["exercise_key"]] == "back")


MAIN = {f"row{i}": "back" for i in range(12)} | {f"curl{i}": "biceps" for i in range(6)} | {f"sq{i}": "quads" for i in range(6)}


# ---------- the trimming rules ----------

def test_a_plan_under_the_cap_is_left_alone():
    days = [day(ex("row0", 4, 1), ex("row1", 4, 2), ex("curl0", 3, 3))]
    trim = enforce_weekly_cap(days, MAIN)
    assert not trim.changed and trim.unresolved == [] and days[0]["exercises"][0]["sets"] == 4


def test_sets_come_off_the_heaviest_exercise_first_and_only_as_far_as_needed():
    days = [day(ex("row0", 5, 1), ex("row1", 4, 2), ex("row2", 4, 3), ex("row3", 4, 4), ex("curl0", 3, 5))]    # back: 17 sets
    days.append(day(ex("row4", 4, 1), ex("row5", 3, 2), ex("curl1", 3, 3)))                                    # back: 24 in total
    trim = enforce_weekly_cap(days, MAIN)
    assert sets_of(days, MAIN) == CAP == 20 and trim.sets_removed == 4 and trim.exercises_removed == 0
    # by hand: row0 5->4 first (the heaviest), then the 4-set ties lose from the LATER positions: row3, row2, row1
    assert [e["sets"] for e in days[0]["exercises"][:4]] == [4, 3, 3, 3] and [e["sets"] for e in days[1]["exercises"][:2]] == [4, 3]
    assert all(e["sets"] >= MIN_SETS for d in days for e in d["exercises"])
    assert all(e["sets"] == 3 for d in days for e in d["exercises"] if e["exercise_key"].startswith("curl"))    # another muscle is untouched


def test_the_trim_flattens_volume_instead_of_gutting_one_exercise():
    days = [day(ex("row0", 5, 1), ex("row1", 5, 2), ex("row2", 5, 3), ex("row3", 5, 4), ex("curl0", 3, 5))]    # back: 20, add more below
    days.append(day(ex("row4", 5, 1), ex("row5", 5, 2), ex("curl1", 3, 3)))                                    # back: 30
    enforce_weekly_cap(days, MAIN)
    back = [e["sets"] for d in days for e in d["exercises"] if main_of(e) == "back"]
    assert sum(back) == 20 and max(back) - min(back) <= 1          # 30 sets over 6 exercises: 3 or 4 each, never one at 2 and one at 5


def main_of(e):
    return MAIN[e["exercise_key"]]


def test_when_every_exercise_is_at_the_minimum_whole_exercises_go_lowest_priority_first():
    days = [day(*[ex(f"row{i}", MIN_SETS, i + 1) for i in range(6)], ex("curl0", 3, 7)),           # 6 rows at 2 sets = 12
            day(*[ex(f"row{i}", MIN_SETS, i - 5) for i in range(6, 12)], ex("curl1", 3, 7))]       # 12 more = 24 back sets
    trim = enforce_weekly_cap(days, MAIN)
    assert sets_of(days, MAIN) == 20 and trim.exercises_removed == 2 and trim.sets_removed == 4
    for d in days:
        assert [e["position"] for e in d["exercises"]] == list(range(1, len(d["exercises"]) + 1))          # renumbered
        assert d["exercises"][-1]["exercise_key"].startswith("curl")                                         # the other muscle is still there
    assert days[1]["exercises"][0]["exercise_key"] == "row6"                                                 # the FIRST exercises of the day stay


def test_a_day_never_drops_below_the_minimum_number_of_exercises():
    days = [day(*[ex(f"row{i}", MIN_SETS, i + 1) for i in range(MIN_DAY_EXERCISES)]) for _ in range(5)]       # 5 days of 3 rows: 30 back sets, cannot trim
    trim = enforce_weekly_cap(days, MAIN)
    assert trim.exercises_removed == 0 and trim.unresolved == ["back"]
    assert all(len(d["exercises"]) == MIN_DAY_EXERCISES for d in days) and sets_of(days, MAIN) == 30             # reported, never hidden


def test_removal_takes_from_the_day_with_the_most_work_for_that_muscle():
    heavy = day(*[ex(f"row{i}", MIN_SETS, i + 1) for i in range(8)])                                   # 8 rows: 16 sets
    light = day(*[ex(f"row{i}", MIN_SETS, i - 7) for i in range(8, 12)], ex("sq0", 3, 5), ex("sq1", 3, 6))   # 4 rows: 8 sets   (24 total)
    enforce_weekly_cap([heavy, light], MAIN)
    assert len(heavy["exercises"]) == 6 and len(light["exercises"]) == 6


def test_only_the_main_muscle_counts():
    main = {"a": "chest", "b": "chest"}
    days = [day(ex("a", 5, 1), ex("b", 5, 2)) for _ in range(3)]            # chest 30 sets, even if an exercise also lists triceps
    enforce_weekly_cap(days, main)
    assert sum(e["sets"] for d in days for e in d["exercises"]) == 20


def test_rest_days_are_skipped_and_the_result_is_deterministic():
    def make():
        return [day(ex("row0", 5, 1), ex("row1", 5, 2), ex("row2", 5, 3), ex("row3", 5, 4), ex("row4", 5, 5)), day(rest=True), day(ex("row5", 5, 1))]
    a, b = make(), make()
    enforce_weekly_cap(a, MAIN)
    enforce_weekly_cap(b, MAIN)
    assert a == b and a[1]["exercises"] == []


# ---------- inside build_payload ----------

PATTERNS = {"push_horizontal": ("chest", "triceps"), "push_vertical": ("shoulders", "triceps"), "pull_horizontal": ("back", "biceps"),
            "pull_vertical": ("back", "biceps"), "squat": ("quads", "glutes"), "hinge": ("hamstrings", "glutes"), "lunge": ("quads", "glutes"), "core": ("abs",)}


def library():
    out, n = {}, 0
    for pattern, muscles in PATTERNS.items():
        for i in range(8):
            n += 1
            key = f"{pattern}_{i}"
            out[key] = ExerciseOption(n, key, key.replace("_", " ").title(), muscles, (), "both", "beginner", pattern, ("cue",), (), "ready")
    return out


def picks(split, per_day):
    lib = library()
    out = []
    for d in split.days:
        keys = [k for k, o in lib.items() if o.movement_pattern in d.patterns and set(o.muscle_groups[:1]) & set(d.muscles)]
        out.append(DayPick(d.label, keys[:per_day]))
    return out


def test_a_six_day_plan_with_eight_exercises_a_day_is_brought_under_the_cap():
    split = split_by_key("ppl_6")
    lib = library()
    payload = build_payload(split, picks(split, 8), lib, level="advanced", goal="muscle_gain", pace="normal", flagged=False, week_start=date(2026, 11, 9))
    assert max(weekly_sets(payload, lib).values()) <= CAP
    assert validate_payload(payload, set(lib)) == []
    vt = payload["volume_trimmed"]
    assert vt["cap"] == CAP and vt["sets_removed"] > 0 and vt["unresolved"] == []


def test_a_small_plan_has_no_trim_note():
    split = split_by_key("full_body_2")
    lib = library()
    payload = build_payload(split, picks(split, 4), lib, level="beginner", goal="general_fitness", pace="normal", flagged=False, week_start=date(2026, 11, 9))
    assert payload["volume_trimmed"] is None


def test_the_day_length_is_worked_out_after_the_trim():
    split = split_by_key("ppl_6")
    lib = library()
    payload = build_payload(split, picks(split, 8), lib, level="advanced", goal="muscle_gain", pace="normal", flagged=False, week_start=date(2026, 11, 9))
    from app.calc.session_time import estimate_day_minutes
    for d in payload["days"]:
        if not d["is_rest"]:
            assert d["minutes"] == estimate_day_minutes([(e["sets"], e["rest_sec"]) for e in d["exercises"]])


def test_focus_sets_added_never_goes_negative_and_the_cap_still_holds():
    split = split_by_key("ppl_6")
    lib = library()
    payload = build_payload(split, picks(split, 8), lib, level="advanced", goal="muscle_gain", pace="normal", flagged=False, week_start=date(2026, 11, 9),
                            focus=("back", "chest"))
    assert payload["focus_sets_added"] >= 0 and max(weekly_sets(payload, lib).values()) <= CAP
