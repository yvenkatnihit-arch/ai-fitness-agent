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
    ],
)
def test_check_lists_match(column, python_values):
    assert sql_values(column) == set(python_values)


def test_injury_areas_match():
    assert sql_array("injury_areas") == set(v.INJURY_AREAS)
