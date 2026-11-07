"""Reading the user's active workout plan (as the signed-in user, under RLS)."""

from psycopg import Connection

from app.calc.session_time import estimate_day_minutes


def read_active_plan(conn: Connection) -> dict | None:
    """The active plan with its seven days and exercises, or None. RLS limits every row to the caller."""
    plan = conn.execute(
        "select id, week_start, version, approved_at from public.workout_plans where status = 'active'"
    ).fetchone()
    if plan is None:
        return None
    days = conn.execute(
        "select id, day_of_week, focus, is_rest from public.workout_plan_days where workout_plan_id = %s order by day_of_week",
        (plan[0],),
    ).fetchall()
    rows = conn.execute(
        """select e.plan_day_id, e.position, x.key, x.name, e.sets, e.reps_min, e.reps_max, e.rest_sec,
                  e.target_load_note, x.form_cues
           from public.workout_plan_exercises e join public.exercises x on x.id = e.exercise_id
           where e.plan_day_id = any(%s) order by e.plan_day_id, e.position""",
        ([d[0] for d in days],),
    ).fetchall()
    by_day: dict = {d[0]: [] for d in days}
    for r in rows:
        by_day[r[0]].append({
            "position": r[1], "exercise_key": r[2], "name": r[3], "sets": r[4], "reps_min": r[5], "reps_max": r[6],
            "rest_sec": r[7], "note": r[8], "form_cues": r[9].split("\n"),
        })
    return {
        "id": str(plan[0]), "week_start": plan[1], "version": plan[2], "approved_at": plan[3],
        "days": [
            {"day_of_week": d[1], "focus": d[2], "is_rest": d[3], "exercises": by_day[d[0]],
             "minutes": None if d[3] else estimate_day_minutes([(e["sets"], e["rest_sec"]) for e in by_day[d[0]]])}
            for d in days
        ],
    }
