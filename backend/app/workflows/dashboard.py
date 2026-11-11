"""The dashboard's "today" summary (Step 8.1, D-105): targets against what was logged, today's planned meals and today's workout.

Pure reading and arithmetic in code, as the signed-in user under row-level security. The percentages are computed here, never by the
browser or a model. Numbers are left out for users who must not see them (`focus_on_habits`), the same rule as every other screen."""

from datetime import date
from uuid import UUID

from app.calc.weekdays import day_name
from app.core.time import india_today
from app.db import active_plan
from app.db import meals as meals_repo
from app.db import targets as targets_repo
from app.db.active_meal_plan import read_active_meal_plan
from app.db.transactions import user_transaction
from app.schemas.dashboard import (LoggedMeal, PlanToday, PlannedItem, PlannedMeal, Progress, ProgressOut, TodayOut, WorkoutExercise,
                                   WorkoutToday)
from app.schemas.meal_plans import to_active_meal_plan


def percent_of(eaten: float, target: float) -> int:
    return round(eaten / target * 100) if target > 0 else 0


def progress_for(eaten: dict[str, float], targets: tuple[float, float, float, float]) -> ProgressOut:
    """`targets` = (kcal, protein_g, carbs_g, fat_g)."""
    parts = {}
    for key, target in zip(("kcal", "protein_g", "carbs_g", "fat_g"), targets):
        shown = round(target)          # the same whole numbers the Targets screen shows, so the two never disagree
        parts[key] = Progress(eaten=round(eaten[key], 1), target=shown, percent=percent_of(eaten[key], shown))
    return ProgressOut(**parts)


def totals_of(meals: list[dict]) -> dict[str, float]:
    items = [i for m in meals for i in m["items"]]
    return {k: sum(i[k] for i in items) for k in ("kcal", "protein_g", "carbs_g", "fat_g")}


def today_overview(user_id: UUID, today: date | None = None) -> TodayOut:
    today = today or india_today()
    weekday = today.isoweekday()
    with user_transaction(user_id) as conn:
        target_row = targets_repo.current_targets(conn)
        meals = meals_repo.meals_on(conn, today)
        raw_plan = read_active_meal_plan(conn)
        workout_plan = active_plan.read_active_plan(conn)
    hidden = bool(target_row[6]) if target_row else False      # focus_on_habits

    progress = None
    if target_row and not hidden:
        kcal, protein, fat, carbs = (float(target_row[i]) for i in (0, 1, 2, 3))
        progress = progress_for(totals_of(meals), (kcal, protein, carbs, fat))

    logged = [LoggedMeal(slot=m["slot"], foods=[f"{i['food_name']} ({i['quantity']:g} {i['unit']})" for i in m["items"]]) for m in meals]

    meal_plan = None
    if raw_plan is not None:
        plan = to_active_meal_plan(raw_plan)                       # applies the hidden-numbers rule
        day = next((d for d in plan.days if d.day_of_week == weekday), None)
        if day is not None:
            meal_plan = PlanToday(
                meals=[PlannedMeal(slot=m.slot, items=[PlannedItem(name=i.name, text=i.text, kcal=i.kcal) for i in m.items]) for m in day.meals],
                kcal=None if hidden or not day.totals else day.totals.get("kcal"))

    workout = None
    if workout_plan is not None:
        day = next((d for d in workout_plan["days"] if d["day_of_week"] == weekday), None)
        if day is not None:
            workout = WorkoutToday(rest_day=True) if day["is_rest"] else WorkoutToday(
                rest_day=False, focus=day["focus"], minutes=day["minutes"],
                exercises=[WorkoutExercise(name=e["name"], sets=e["sets"], reps=f"{e['reps_min']}-{e['reps_max']}") for e in day["exercises"]])

    return TodayOut(date=today, weekday=day_name(weekday), numbers_hidden=hidden, progress=progress, logged=logged,
                    meal_plan=meal_plan, workout=workout)
