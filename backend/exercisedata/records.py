"""One row of data/exercises.csv, read exactly as written (checks come later, in checks.py).

Lists use ';' inside a cell (muscles, equipment, injury tags). Form cues use ' | ' between lines.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ["key", "name", "muscle_groups", "equipment", "location", "difficulty", "movement_pattern",
           "form_cues", "contraindications", "ref_id", "reviewed_by", "note"]


@dataclass(frozen=True)
class Exercise:
    key: str
    name: str
    muscle_groups: tuple[str, ...]   # first one = the main muscle
    equipment: tuple[str, ...]       # empty = bodyweight only
    location: str
    difficulty: str
    movement_pattern: str
    cues: tuple[str, ...]
    contraindications: tuple[str, ...]
    ref_id: str                      # Free Exercise DB id, or '' when it has no equivalent
    reviewed_by: str                 # a human signs off the injury tags by filling this
    note: str


def split_list(cell: str, separator: str = ";") -> tuple[str, ...]:
    return tuple(part.strip() for part in cell.split(separator) if part.strip())


def read_exercises(path: Path) -> list[Exercise]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"{path.name}: columns must be exactly {COLUMNS}, got {reader.fieldnames}")
        return [
            Exercise(
                key=row["key"].strip(), name=row["name"].strip(),
                muscle_groups=split_list(row["muscle_groups"]), equipment=split_list(row["equipment"]),
                location=row["location"].strip(), difficulty=row["difficulty"].strip(),
                movement_pattern=row["movement_pattern"].strip(), cues=split_list(row["form_cues"], "|"),
                contraindications=split_list(row["contraindications"]), ref_id=row["ref_id"].strip(),
                reviewed_by=row["reviewed_by"].strip(), note=row["note"].strip(),
            )
            for row in reader
        ]
