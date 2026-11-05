import re
from pathlib import Path

from app.safety.safety_config import SCREENING_FLAGS

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase" / "migrations" / "20261105130000_screening_goals_targets.sql"
)


def test_health_screening_columns_match_safety_config_flags():
    # If someone adds a flag in safety_config.py, the database must get a column too (and vice versa).
    sql = MIGRATION.read_text(encoding="utf-8")
    table = re.search(r"create table public\.health_screening \((.*?)\n\);", sql, re.S).group(1)
    columns = set(re.findall(r"^\s+(\w+)\s+boolean not null default false", table, re.M))
    assert columns == set(SCREENING_FLAGS)
