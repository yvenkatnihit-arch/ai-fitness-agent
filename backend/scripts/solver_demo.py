"""Try the portion solver on a real day: real foods, real engine targets, no LLM, nothing saved.

Run from backend/:
  uv run python scripts/solver_demo.py [diet] [profile]
  diet: vegan | vegetarian | eggetarian | non_vegetarian      (default vegetarian)
  profile: fatloss_f | muscle_m | maintain_o                  (default fatloss_f)
  pick: first | protein                                       (default first; 'protein' = most protein per kcal)
(PowerShell: set $env:PYTHONPATH='.' first.) Dishes are the first allowed choice per role: variety comes from the
dish picker in step 6.7c, so this shows the SOLVER only.
"""

import sys

from app.calc.engine import BodyProfile, calculate_targets
from app.calc.meal_pool import SLOTS, build_pool
from app.calc.meal_solver import MealItem, day_targets, solve_day
from app.db.meal_foods import list_pool_foods
from app.db.pool import close_pool
from app.db.transactions import admin_transaction

PROFILES = {
    "fatloss_f": BodyProfile(weight_kg=58, height_cm=162.5, age_years=31, sex="female", activity_level="light",
                             goal="fat_loss", screening_flags=frozenset(), pace="normal"),
    "muscle_m": BodyProfile(weight_kg=80, height_cm=178, age_years=27, sex="male", activity_level="moderate",
                            goal="muscle_gain", screening_flags=frozenset(), pace="normal"),
    "maintain_o": BodyProfile(weight_kg=70, height_cm=170, age_years=40, sex="other", activity_level="sedentary",
                              goal="general_fitness", screening_flags=frozenset(), pace="normal"),
}

diet = sys.argv[1] if len(sys.argv) > 1 else "vegetarian"
name = sys.argv[2] if len(sys.argv) > 2 else "fatloss_f"
pick = sys.argv[3] if len(sys.argv) > 3 else "first"
profile = PROFILES[name]
engine = calculate_targets(profile)
targets = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)

with admin_transaction("demo: read foods") as conn:
    foods = list_pool_foods(conn)
pool = build_pool(foods, diet)
def choose(choices):
    return max(choices, key=lambda f: f.protein_g / max(f.kcal, 1)) if pick == "protein" else choices[0]


items = [MealItem(slot, role, choose(choices)) for slot in SLOTS for role, choices in pool[slot].roles.items() if choices]

print(f"{diet} | {name} | pick={pick} | target {targets.kcal:.0f} kcal (band {targets.kcal_min:.0f}-{targets.kcal_max:.0f}), "
      f"protein {targets.protein_g:.0f} g (cap {targets.protein_max_g:.0f}), carbs {targets.carbs_g:.0f} g, fat {targets.fat_g:.0f} g\n")
result = solve_day(items, targets)
print("status:", result.status)
slot = None
for s in result.items:
    if s.slot != slot:
        slot = s.slot
        print(f"\n{slot}  ({result.slot_kcal[slot]:.0f} kcal)")
    n = s.nutrition
    print(f"   {s.role:10s} {s.food_name[:34]:34s} {s.portion.text:22s} {n.kcal:6.0f} kcal  P{n.protein_g:5.1f} C{n.carbs_g:5.1f} F{n.fat_g:5.1f}")
t = result.totals
print(f"\nTOTAL {t.kcal:.0f} kcal  P{t.protein_g:.0f} C{t.carbs_g:.0f} F{t.fat_g:.0f}   "
      f"({', '.join(f'{k} {v:.0f}%' for k, v in result.percent_of_target.items())})")
for issue in result.issues:
    print("ISSUE:", issue)
close_pool()
