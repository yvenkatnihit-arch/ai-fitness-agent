"""Load data/exercises_validated.csv into Supabase: public.exercises (Step 5.3, D-041).

    uv run python -m exercisedata.build            # first: regenerate the validated CSV
    uv run python -m exercisedata.load --dry-run   # show what would change, then roll back
    uv run python -m exercisedata.load             # load

Safe to re-run (idempotent): exercises are upserted by `key`, so ids never change. Everything
happens in ONE transaction: if any row fails, nothing is saved. Exercises that are in the database
but no longer in the CSV are reported, never deleted (workout plans and logs may point to them).
"""

import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from exercisedata.build import VALIDATED
from exercisedata.records import split_list


@dataclass(frozen=True)
class ExerciseRow:
    key: str
    name: str
    muscle_groups: list[str]
    equipment: list[str]
    location: str
    difficulty: str
    movement_pattern: str
    form_cues: str                 # the cues, one per line
    contraindications: list[str]
    source_ref: str | None
    review_status: str


def to_exercise_row(row: dict) -> ExerciseRow:
    if row["status"] not in ("ready", "review"):
        raise ValueError(f"{row['key']}: status {row['status']!r} must not be in the validated file")
    exercise = ExerciseRow(
        key=row["key"], name=row["name"], muscle_groups=list(split_list(row["muscle_groups"])),
        equipment=list(split_list(row["equipment"])), location=row["location"], difficulty=row["difficulty"],
        movement_pattern=row["movement_pattern"], form_cues="\n".join(split_list(row["form_cues"], "|")),
        contraindications=list(split_list(row["contraindications"])), source_ref=row["ref_id"] or None,
        review_status=row["status"],
    )
    if not 1 <= len(exercise.form_cues) <= 400:
        raise ValueError(f"{exercise.key}: cues must be 1-400 characters in total")
    return exercise


def read_validated(path: Path = VALIDATED) -> list[ExerciseRow]:
    with path.open(encoding="utf-8", newline="") as handle:
        exercises = [to_exercise_row(row) for row in csv.DictReader(handle)]
    keys = [e.key for e in exercises]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise ValueError(f"duplicate keys: {duplicates}")
    return exercises


UPSERT = """
insert into public.exercises (key, name, muscle_groups, equipment, location, difficulty, movement_pattern,
                              form_cues, contraindications, source_ref, review_status)
values (%(key)s, %(name)s, %(muscle_groups)s, %(equipment)s, %(location)s, %(difficulty)s, %(movement_pattern)s,
        %(form_cues)s, %(contraindications)s, %(source_ref)s, %(review_status)s)
on conflict (key) do update set
  name = excluded.name, muscle_groups = excluded.muscle_groups, equipment = excluded.equipment,
  location = excluded.location, difficulty = excluded.difficulty, movement_pattern = excluded.movement_pattern,
  form_cues = excluded.form_cues, contraindications = excluded.contraindications,
  source_ref = excluded.source_ref, review_status = excluded.review_status
returning id, (xmax = 0) as inserted
"""


@dataclass
class LoadResult:
    inserted: int = 0
    updated: int = 0
    stale: tuple[str, ...] = ()
    ids: dict[str, int] = field(default_factory=dict)


def load_exercises(conn: psycopg.Connection, exercises: list[ExerciseRow]) -> LoadResult:
    """Upsert every exercise. The caller commits or rolls back."""
    result = LoadResult()
    for exercise in exercises:
        exercise_id, inserted = conn.execute(UPSERT, exercise.__dict__).fetchone()
        result.ids[exercise.key] = exercise_id
        if inserted:
            result.inserted += 1
        else:
            result.updated += 1
    rows = conn.execute("select key from public.exercises where not (key = any(%s)) order by key",
                        ([e.key for e in exercises],)).fetchall()
    result.stale = tuple(r[0] for r in rows)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show what would change, then roll back")
    args = parser.parse_args()

    from app.core.config import get_settings  # only needed when talking to the database

    exercises = read_validated()
    with psycopg.connect(get_settings().database_url.get_secret_value(), connect_timeout=10) as conn:
        result = load_exercises(conn, exercises)
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    verb = "would be" if args.dry_run else "were"
    print(f"{len(exercises)} exercises: {result.inserted} {verb} inserted, {result.updated} {verb} updated")
    ready = sum(e.review_status == "ready" for e in exercises)
    print(f"review status: {ready} ready, {len(exercises) - ready} review")
    if result.stale:
        print(f"in the database but not in the CSV (kept, not deleted): {', '.join(result.stale)}")
    if args.dry_run:
        print("dry run: nothing was saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
