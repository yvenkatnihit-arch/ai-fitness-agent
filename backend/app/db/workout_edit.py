"""Reading and rewriting the active workout plan for a hand edit (admin: the plan tables are server-written, D-027).

Every function takes an admin connection, which BYPASSES row level security, so each one filters by user_id itself. The day rows
are KEPT (only their label and the exercises under them change), because a workout log can point at a plan day.
"""

from typing import Any
from uuid import UUID

from psycopg import Connection


def read_active_for_edit(conn: Connection, user_id: UUID, lock: bool = True) -> tuple[UUID, dict[int, UUID], dict[str, Any]] | None:
    """(plan id, {weekday: day row id}, payload-shaped plan) for the user's active plan, or None. With `lock` the plan row is locked
    so two edits at once cannot overwrite each other (a read-only look does not need it)."""
    plan = conn.execute(
        "select id, week_start from public.workout_plans where user_id = %s and status = 'active'" + (" for update" if lock else ""),
        (user_id,),
    ).fetchone()
    if plan is None:
        return None
    days = conn.execute(
        "select id, day_of_week, focus, is_rest from public.workout_plan_days where workout_plan_id = %s and user_id = %s order by day_of_week",
        (plan[0], user_id),
    ).fetchall()
    rows = conn.execute(
        """select e.plan_day_id, e.position, x.key, x.name, e.sets, e.reps_min, e.reps_max, e.rest_sec, e.target_load_note
           from public.workout_plan_exercises e join public.exercises x on x.id = e.exercise_id
           where e.user_id = %s and e.plan_day_id = any(%s) order by e.plan_day_id, e.position""",
        (user_id, [d[0] for d in days]),
    ).fetchall()
    by_day: dict[Any, list[dict[str, Any]]] = {d[0]: [] for d in days}
    for r in rows:
        by_day[r[0]].append({"exercise_key": r[2], "name": r[3], "position": r[1], "sets": r[4], "reps_min": r[5],
                             "reps_max": r[6], "rest_sec": r[7], "note": r[8]})
    payload = {
        "kind": "workout_plan", "version": 1, "week_start": plan[1].isoformat(),
        "days": [{"day_of_week": d[1], "focus": d[2], "is_rest": d[3], "exercises": by_day[d[0]]} for d in days],
    }
    return plan[0], {d[1]: d[0] for d in days}, payload


def write_plan(conn: Connection, user_id: UUID, day_ids: dict[int, UUID], payload: dict[str, Any], exercise_ids: dict[str, int]) -> None:
    """Make the stored plan match `payload`: update each day's label, replace its exercises. One transaction (the caller's)."""
    for day in payload["days"]:
        day_id = day_ids[day["day_of_week"]]
        conn.execute("update public.workout_plan_days set focus = %s, is_rest = %s where id = %s and user_id = %s",
                     (day["focus"], day["is_rest"], day_id, user_id))
        conn.execute("delete from public.workout_plan_exercises where plan_day_id = %s and user_id = %s", (day_id, user_id))
        for e in day["exercises"]:
            conn.execute(
                """insert into public.workout_plan_exercises
                     (plan_day_id, user_id, exercise_id, position, sets, reps_min, reps_max, rest_sec, target_load_note)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (day_id, user_id, exercise_ids[e["exercise_key"]], e["position"], e["sets"], e["reps_min"], e["reps_max"],
                 e["rest_sec"], e["note"]),
            )
