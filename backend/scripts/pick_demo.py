"""Try the exercise picker for a made-up user, with the REAL library and the REAL Gemini (about a cent).

Run from backend/:
  uv run python scripts/pick_demo.py [split_key] [level] [place] [injury,injury]
  e.g.  uv run python scripts/pick_demo.py ppl_3 intermediate gym knee
(PowerShell: set $env:PYTHONPATH='.' first.) Nothing is saved.
"""

import sys

from app.calc.exercise_filter import ExerciseNeeds, filter_exercises
from app.calc.splits import split_by_key
from app.db.exercises import list_exercises
from app.db.pool import close_pool
from app.db.transactions import admin_transaction
from app.workflows.pick_exercises import pick_exercises

key = sys.argv[1] if len(sys.argv) > 1 else "ppl_3"
level = sys.argv[2] if len(sys.argv) > 2 else "intermediate"
place = sys.argv[3] if len(sys.argv) > 3 else "gym"
injuries = frozenset(filter(None, (sys.argv[4] if len(sys.argv) > 4 else "knee").split(",")))

with admin_transaction("demo: read exercise library") as conn:
    library = list_exercises(conn)
allowed = filter_exercises(library, ExerciseNeeds(place, level, injuries, frozenset()))   # type: ignore[arg-type]
names = {o.key: o.name for o in library}
print(f"{key} | {level} | {place} | injuries: {sorted(injuries) or 'none'} | {len(allowed)} of {len(library)} exercises allowed\n")

for day in pick_exercises(split_by_key(key), allowed, level, "muscle_gain"):
    print(f"{day.label}  [{day.source}]" + (f"  note: {day.note}" if day.note else ""))
    for k in day.keys:
        print(f"   - {names[k]}  ({k})")
close_pool()
