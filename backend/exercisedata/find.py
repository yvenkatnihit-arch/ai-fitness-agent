"""Find an exercise's exact Free Exercise DB id, to cite it in data/exercises.csv.

    uv run python -m exercisedata.find "push up" "goblet squat"
"""

import sys

from exercisedata.freedb import ExerciseRef, default_path, read_free_exercise_db


def search(refs: list[ExerciseRef], query: str) -> list[ExerciseRef]:
    words = query.lower().replace("-", " ").split()
    hits = [r for r in refs if all(w in r.name.lower().replace("-", " ") for w in words)]
    return sorted(hits, key=lambda r: (len(r.name), r.name))  # shortest (most generic) names first


def describe(r: ExerciseRef) -> str:
    muscles = ", ".join(r.primary_muscles) + (f" (+ {', '.join(r.secondary_muscles)})" if r.secondary_muscles else "")
    return f"  {r.id:<40} {r.level:<12} {str(r.equipment):<14} {muscles}"


def main(queries: list[str]) -> None:
    refs = read_free_exercise_db(default_path())
    for query in queries:
        hits = search(refs, query)
        print(f"\n## {query}  ({len(hits)} matches)")
        for r in hits[:8]:
            print(describe(r))


if __name__ == "__main__":
    main(sys.argv[1:])
