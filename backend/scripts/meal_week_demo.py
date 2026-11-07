"""Try the whole meal workflow: real foods, real engine targets, REAL Gemini (mid tier, about a cent), nothing saved.

Run from backend/:
  uv run python scripts/meal_week_demo.py [diet] [profile] [model|fallback] [dislike,dislike]
  diet: vegan | vegetarian | eggetarian | non_vegetarian        (default vegetarian)
  profile: fatloss_f | muscle_m | maintain_o | kidney_m         (default fatloss_f)
  model|fallback: 'fallback' switches Gemini off so you see the code-only week (default model)
(PowerShell: set $env:PYTHONPATH='.' first.) Test data only: the free Gemini tier may be used by Google to improve its products.
"""

import sys

from app.calc.engine import BodyProfile, calculate_targets
from app.calc.meal_solver import day_targets
from app.calc.meal_week import emphasis_for
from app.db.meal_foods import list_pool_foods
from app.db.pool import close_pool
from app.db.transactions import admin_transaction
from app.llm.client import LLMBusy
from app.workflows.pick_meals import pick_meals

PROFILES = {
    "fatloss_f": BodyProfile(weight_kg=58, height_cm=162.5, age_years=31, sex="female", activity_level="light",
                             goal="fat_loss", screening_flags=frozenset(), pace="normal"),
    "muscle_m": BodyProfile(weight_kg=80, height_cm=178, age_years=27, sex="male", activity_level="moderate",
                            goal="muscle_gain", screening_flags=frozenset(), pace="normal"),
    "maintain_o": BodyProfile(weight_kg=70, height_cm=170, age_years=40, sex="other", activity_level="sedentary",
                              goal="general_fitness", screening_flags=frozenset(), pace="normal"),
    "kidney_m": BodyProfile(weight_kg=82, height_cm=176, age_years=50, sex="male", activity_level="moderate",
                            goal="fat_loss", screening_flags=frozenset({"kidney"}), pace="normal"),
}

diet = sys.argv[1] if len(sys.argv) > 1 else "vegetarian"
name = sys.argv[2] if len(sys.argv) > 2 else "fatloss_f"
mode = sys.argv[3] if len(sys.argv) > 3 else "model"
dislikes = [d for d in (sys.argv[4] if len(sys.argv) > 4 else "").split(",") if d]
profile = PROFILES[name]
engine = calculate_targets(profile)
targets = day_targets(engine, weight_kg=profile.weight_kg, sex=profile.sex, flags=profile.screening_flags)
emphasis = emphasis_for(engine.protein_g, engine.calorie_target_kcal, profile.screening_flags)


def down(prompt):
    raise LLMBusy()


with admin_transaction("demo: read foods") as conn:
    foods = list_pool_foods(conn)
plan = pick_meals(foods, diet, dislikes, targets, profile.goal, emphasis, ask=down if mode == "fallback" else None)

print(f"{diet} | {name} | target {targets.kcal:.0f} kcal, protein {targets.protein_g:.0f} g | {len(plan.slots)} meals/day | "
      f"portion scale {plan.portion_scale} | emphasis {emphasis} | model called: {plan.model_called}, repair asked: {plan.repair_asked}\n")
for d in plan.days:
    t = d.solution.totals
    print(f"Day {d.day} [{d.source}, {d.solution.status}]  {t.kcal:.0f} kcal  P{t.protein_g:.0f} C{t.carbs_g:.0f} F{t.fat_g:.0f}  "
          f"({', '.join(f'{k} {v:.0f}%' for k, v in d.solution.percent_of_target.items())})")
    slot = None
    for item in d.solution.items:
        if item.slot != slot:
            slot = item.slot
            print(f"   {slot}: ", end="")
        print(f"{item.food_name} {item.portion.text}; ", end="")
        # newline when the next item starts a new slot is handled above by the next label
    print()
    for issue in d.solution.issues:
        print("   ISSUE:", issue)
close_pool()
