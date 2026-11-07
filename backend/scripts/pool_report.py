"""How many choices does each diet type have per meal and role? Reads the real foods; saves nothing.

Run from backend/:  uv run python scripts/pool_report.py [dislike1,dislike2]
(PowerShell: set $env:PYTHONPATH='.' first.) Thin roles (fewer than 3 choices) are marked with !.
"""

import sys

from app.calc.meal_pool import ALLOWED_DIET_CLASSES, SLOTS, build_pool
from app.db.meal_foods import list_pool_foods
from app.db.pool import close_pool
from app.db.transactions import admin_transaction

dislikes = [d for d in (sys.argv[1] if len(sys.argv) > 1 else "").split(",") if d]
with admin_transaction("report: read foods") as conn:
    foods = list_pool_foods(conn)
print(f"{len(foods)} foods loaded; dislikes: {dislikes or 'none'}\n")
for diet in ALLOWED_DIET_CLASSES:
    pool = build_pool(foods, diet, dislikes)
    print(diet)
    for slot in SLOTS:
        p = pool[slot]
        parts = [f"{role} {len(items)}{'!' if role in p.thin or role in p.missing else ''}" for role, items in p.roles.items()]
        print(f"  {slot:14s} " + "   ".join(parts) + (f"   MISSING: {', '.join(p.missing)}" if p.missing else ""))
close_pool()
