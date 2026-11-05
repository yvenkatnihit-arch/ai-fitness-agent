import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def test_migration_files_are_named_timestamp_underscore_name():
    # The Supabase CLI runs files in name order, so the 14-digit timestamp prefix matters.
    files = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    assert files, "no migrations found"
    bad = [name for name in files if not re.fullmatch(r"\d{14}_[a-z0-9_]+\.sql", name)]
    assert bad == []


def test_every_created_table_enables_rls():
    # CLAUDE.md: every user-owned table has RLS. Checked statically for every migration file.
    for path in MIGRATIONS.glob("*.sql"):
        sql = path.read_text(encoding="utf-8").lower()
        for table in re.findall(r"create table (public\.\w+)", sql):
            assert f"alter table {table} enable row level security" in sql, f"{path.name}: {table}"


def test_injury_tags_match_between_screening_and_exercises():
    # A user's injury_areas are matched against exercise contraindications (Phase 5),
    # so both columns must allow exactly the same tags.
    sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted(MIGRATIONS.glob("*.sql")))
    tag_lists = re.findall(r"(?:injury_areas|contraindications) <@ array\[([^\]]+)\]", sql)
    assert len(tag_lists) == 2
    as_sets = [set(re.findall(r"'(\w+)'", tags)) for tags in tag_lists]
    assert as_sets[0] == as_sets[1]
