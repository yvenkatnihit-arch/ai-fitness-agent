"""Read-only tools for the "my plan" specialist (Step 7.12a, D-103): the user's OWN targets, meal plan, workout plan and today's log.

Every tool runs as the signed-in user under row-level security (identity comes from the harness, never from the model), reads saved
data only (no LLM, no recalculation by the model) and changes nothing. The same rule as the screens applies: for a user who must not
see numbers (eating-disorder history, `focus_on_habits`) calories and macros are removed HERE, so the model cannot repeat them.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.context import RunContext
from app.agents.tools import Tool
from app.calc.week_summary import last_days, logged_days_only, remaining_today, summarize_week
from app.calc.weekdays import DayName, day_name, resolve_day
from app.core.time import india_today
from app.db import active_plan
from app.db import meals as meals_repo
from app.db import targets as targets_repo
from app.db.active_meal_plan import read_active_meal_plan
from app.db.transactions import user_transaction
from app.workflows import weight_log
from app.schemas.meal_plans import to_active_meal_plan
from app.schemas.targets import to_targets_out

NO_TARGETS = "No targets yet: the user has not finished onboarding."
NO_MEAL_PLAN = "The user has no approved meal plan yet. They can make one on the Meal plan screen."
NO_WORKOUT_PLAN = "The user has no approved workout plan yet. They can make one on the Workout plan screen."
MAX_CUES = 3


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DayArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: DayName = Field(default="today", description="a weekday name, or today, tomorrow or yesterday")


def _targets(ctx: RunContext, args: NoArgs) -> dict[str, Any]:
    with user_transaction(ctx.user_id) as conn:
        row = targets_repo.current_targets(conn)
    if row is None:
        return {"error": NO_TARGETS}
    kcal, protein, fat, carbs, reasons, doctor_note, habits = row
    out = to_targets_out(float(kcal), float(protein), float(fat), float(carbs), reasons, doctor_note, habits)
    data = out.model_dump(exclude_none=True)          # numbers are absent for users who must not see them
    if habits:
        data["note"] = "This user's plan focuses on regular balanced meals, so no calorie or macro numbers may be shared."
    return data


def _meal_day(ctx: RunContext, args: DayArgs) -> dict[str, Any]:
    wanted = resolve_day(args.day, india_today())
    with user_transaction(ctx.user_id) as conn:
        raw = read_active_meal_plan(conn)
    if raw is None:
        return {"error": NO_MEAL_PLAN}
    plan = to_active_meal_plan(raw)                    # applies the hidden-numbers rule
    day = next((d for d in plan.days if d.day_of_week == wanted), None)
    if day is None:
        return {"day": day_name(wanted), "error": "This day is not in the user's meal plan."}
    return {"day": day_name(wanted), "plan_week_starts": plan.week_start.isoformat(),
            "meals": [{"slot": m.slot, "items": [i.model_dump(exclude_none=True, exclude={"position", "grams"}) for i in m.items]} for m in day.meals],
            **({"totals": day.totals} if day.totals and not plan.numbers_hidden else {})}


def _workout_day(ctx: RunContext, args: DayArgs) -> dict[str, Any]:
    wanted = resolve_day(args.day, india_today())
    with user_transaction(ctx.user_id) as conn:
        plan = active_plan.read_active_plan(conn)
    if plan is None:
        return {"error": NO_WORKOUT_PLAN}
    day = next((d for d in plan["days"] if d["day_of_week"] == wanted), None)
    if day is None:
        return {"day": day_name(wanted), "error": "This day is not in the user's workout plan."}
    if day["is_rest"]:
        return {"day": day_name(wanted), "rest_day": True}
    return {"day": day_name(wanted), "rest_day": False, "focus": day["focus"], "about_minutes": day["minutes"],
            "exercises": [{"name": e["name"], "sets": e["sets"], "reps": f"{e['reps_min']}-{e['reps_max']}", "rest_seconds": e["rest_sec"],
                           **({"note": e["note"]} if e["note"] else {}), "form_cues": e["form_cues"][:MAX_CUES]} for e in day["exercises"]]}


def _logged_today(ctx: RunContext, args: NoArgs) -> dict[str, Any]:
    with user_transaction(ctx.user_id) as conn:
        meals = meals_repo.meals_on(conn, india_today())
        row = targets_repo.current_targets(conn)
    hidden = bool(row[6]) if row else False             # focus_on_habits
    if not meals:
        out = {"meals_logged": 0, "note": "Nothing logged today yet. They can log a meal on the Log a meal screen or tell the chat what they ate."}
        if row and not hidden:
            out["left_today_negative_means_over"] = remaining_today({k: 0.0 for k in ("kcal", "protein_g", "carbs_g", "fat_g")}, float(row[0]), float(row[1]), float(row[3]), float(row[2]))
        return out
    foods = [{"slot": m["slot"], "foods": [f"{i['food_name']} ({i['quantity']:g} {i['unit']})" for i in m["items"]]} for m in meals]
    if hidden:
        return {"meals_logged": len(meals), "meals": foods, "note": "No calorie or macro numbers may be shared for this user."}
    items = [i for m in meals for i in m["items"]]
    totals = {k: round(sum(i[k] for i in items), 1) for k in ("kcal", "protein_g", "carbs_g", "fat_g")}
    out = {"meals_logged": len(meals), "meals": foods, "totals_so_far": totals}
    if row:                                            # row = calorie, protein, fat, carbs targets (worked out by code, shown on the Targets screen)
        left = remaining_today(totals, float(row[0]), float(row[1]), float(row[3]), float(row[2]))
        out["left_today_negative_means_over"] = left
    return out


def _logged_week(ctx: RunContext, args: NoArgs) -> dict[str, Any]:
    today = india_today()
    days = last_days(today)
    with user_transaction(ctx.user_id) as conn:
        totals = meals_repo.daily_totals(conn, days[0], today)
        row = targets_repo.current_targets(conn)
    hidden = bool(row[6]) if row else False
    summary = summarize_week(totals, today, float(row[0]) if row else None, float(row[1]) if row else None)
    if hidden:
        return {**logged_days_only(summary["days"]), "note": "No calorie or macro numbers may be shared for this user."}
    if summary["days_logged"] == 0:
        summary["note"] = "Nothing logged in the last 7 days. They can log meals on the Log a meal screen."
    return summary


def _weight(ctx: RunContext, args: NoArgs) -> dict[str, Any]:
    """The weight trend, worked out by code (app.calc.weight_trend). Nothing for a user who must not see numbers."""
    history = weight_log.read(ctx.user_id, 90)
    if history.numbers_hidden:
        return {"note": "This user's plan focuses on regular balanced meals, so no weights may be shared."}
    if not history.entries:
        return {"note": "No weight has been logged yet. They can log one on the Home screen."}
    out = history.model_dump(exclude_none=True, exclude={"numbers_hidden", "entries"}, mode="json")
    out["recent_weigh_ins"] = [{"date": e.date.isoformat(), "weight_kg": e.weight_kg} for e in history.entries[-5:]]
    return out


GET_MY_TARGETS = Tool("get_my_targets", "The user's own daily calorie and macro targets (calories, protein, fat, carbs) and why.",
                      NoArgs, _targets, scope="read")
GET_MY_MEAL_PLAN_DAY = Tool("get_my_meal_plan_day", "What the user's approved meal plan says to eat on one day (meals, foods, portions).",
                            DayArgs, _meal_day, scope="read")
GET_MY_WORKOUT_DAY = Tool("get_my_workout_day", "What the user's approved workout plan has on one day (focus, exercises, sets, reps, rest, form cues).",
                          DayArgs, _workout_day, scope="read")
GET_TODAY_LOGGED = Tool("get_today_logged", "What the user has logged eating TODAY and the totals so far.", NoArgs, _logged_today, scope="read")
GET_WEEK_LOGGED = Tool("get_week_logged", "What the user logged eating over the last 7 days, per day, with averages and how many days were near their "
                       "calorie target. Days without a log are not counted as zero.", NoArgs, _logged_week, scope="read")
GET_MY_WEIGHT = Tool("get_my_weight", "The user's own weight progress: latest weight, change since they started, distance to their target weight, "
                     "percent of the way there, weekly rate and recent weigh-ins.", NoArgs, _weight, scope="read")
