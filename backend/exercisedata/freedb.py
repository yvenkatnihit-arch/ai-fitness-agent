"""Read Free Exercise DB (public domain, D-041): used only to CROSS-CHECK our curated exercises.

We read names, level, equipment and muscles. We never copy its instructions or images (the brief
has no images, and our form cues are our own short 2-4 lines).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from fooddata.download import MANIFEST, RAW_DIR

SOURCE_KEY = "free_exercise_db"
LEVELS = {"beginner": "beginner", "intermediate": "intermediate", "expert": "advanced"}  # theirs -> ours


@dataclass(frozen=True)
class ExerciseRef:
    id: str
    name: str
    level: str                  # beginner | intermediate | advanced (our words)
    equipment: str | None       # their words: "dumbbell", "body only", "machine"... (None = not recorded)
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]
    category: str               # strength, stretching, cardio, plyometrics...


def read_free_exercise_db(path: Path) -> list[ExerciseRef]:
    items = json.loads(path.read_text(encoding="utf-8"))
    refs = []
    for item in items:
        if item["level"] not in LEVELS:
            raise ValueError(f"{item['id']}: unknown level {item['level']!r}")
        refs.append(ExerciseRef(
            id=item["id"], name=item["name"], level=LEVELS[item["level"]], equipment=item.get("equipment"),
            primary_muscles=tuple(item["primaryMuscles"]), secondary_muscles=tuple(item["secondaryMuscles"]),
            category=item["category"],
        ))
    ids = [r.id for r in refs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids in Free Exercise DB")
    return refs


def default_path() -> Path:
    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]
    return RAW_DIR / next(s["file"] for s in sources if s["key"] == SOURCE_KEY)
