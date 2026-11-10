"""The allowed values in Python must match the CHECK constraints in the SQL migrations exactly."""

import re
from pathlib import Path
from typing import get_args

import pytest

from app.calc.targets import Goal
from app.calc.tdee import ActivityLevel
from app.core import vocabulary as v
from app.safety.safety_config import Sex

SQL = "\n".join(
    p.read_text(encoding="utf-8")
    for p in sorted((Path(__file__).resolve().parents[2] / "supabase" / "migrations").glob("*.sql"))
)


def sql_values(column: str) -> set[str]:
    """Values in `<column> in ('a', 'b', ...)` (first occurrence)."""
    match = re.search(rf"\b{column}\s+in\s*\(([^)]*)\)", SQL)
    assert match, f"no CHECK list for {column}"
    return set(re.findall(r"'(\w+)'", match.group(1)))


def sql_array(column: str) -> set[str]:
    """Values in `<column> <@ array['a', 'b', ...]` (first occurrence)."""
    match = re.search(rf"\b{column}\s+<@\s+array\[([^\]]*)\]", SQL)
    assert match, f"no array check for {column}"
    return set(re.findall(r"'(\w+)'", match.group(1)))


@pytest.mark.parametrize(
    ("column", "python_values"),
    [
        ("sex", get_args(Sex)),
        ("activity_level", get_args(ActivityLevel)),
        ("goal_type", get_args(Goal)),
        ("diet_type", v.DIET_TYPES),
        ("experience_level", v.EXPERIENCE_LEVELS),
        ("workout_location", v.WORKOUT_LOCATIONS),
        ("movement_pattern", v.MOVEMENT_PATTERNS),
        ("pace", v.PACES),
    ],
)
def test_check_lists_match(column, python_values):
    assert sql_values(column) == set(python_values)


def test_injury_areas_match():
    assert sql_array("injury_areas") == set(v.INJURY_AREAS)


def test_the_cuisine_lists_in_both_tables_match_the_vocabulary():
    """foods.cuisines and profiles.cuisines each have a check list; both must equal Cuisine (a new cuisine is added to all three together)."""
    # Every migration that sets the lists is in the history; the LAST definition of each table's list is the one in force.
    found = re.findall(r"public\.(foods|profiles)\s+add constraint \w+\s+check \(cuisines\s+<@\s+array\[([^\]]*)\]", SQL, flags=re.S)
    latest = {table: set(re.findall(r"'(\w+)'", values)) for table, values in found}      # later migrations overwrite earlier ones
    assert set(latest) == {"foods", "profiles"} and all(values == set(v.CUISINES) for values in latest.values())
