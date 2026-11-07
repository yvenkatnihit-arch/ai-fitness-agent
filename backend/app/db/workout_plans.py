"""Writing an approved workout plan (admin: the plan tables are server-written, D-027).

Every function here takes an admin connection, which BYPASSES row level security, so each one filters by
user_id itself. Callers run them inside ONE admin_transaction so the whole approval is all-or-nothing.
"""

from datetime import date
from typing import Any
from uuid import UUID

from psycopg import Connection


def lock_proposal(conn: Connection, user_id: UUID, proposal_id: UUID) -> tuple | None:
    """The proposal if it is THIS user's, locked until the transaction ends (stops two approvals at once)."""
    return conn.execute(
        "select id, type, status, payload from public.plan_proposals where id = %s and user_id = %s for update",
        (proposal_id, user_id),
    ).fetchone()


def exercise_ids(conn: Connection) -> dict[str, int]:
    return dict(conn.execute("select key, id from public.exercises").fetchall())


def mark_decided(conn: Connection, user_id: UUID, proposal_id: UUID, status: str) -> tuple:
    return conn.execute(
        """update public.plan_proposals set status = %s, decided_at = now()
           where id = %s and user_id = %s and status = 'pending'
           returning id, type, source, summary, status, payload, created_at""",
        (status, proposal_id, user_id),
    ).fetchone()


def activate_workout_plan(conn: Connection, user_id: UUID, week_start: date, payload: dict[str, Any],
                          ids: dict[str, int]) -> UUID:
    """Archive the user's active plan, then write this one as the active plan. Returns the new plan id."""
    conn.execute(
        "update public.workout_plans set status = 'archived' where user_id = %s and status = 'active'", (user_id,)
    )
    version = conn.execute(
        "select coalesce(max(version), 0) + 1 from public.workout_plans where user_id = %s and week_start = %s",
        (user_id, week_start),
    ).fetchone()[0]
    plan_id = conn.execute(
        """insert into public.workout_plans (user_id, week_start, status, version, approved_at)
           values (%s, %s, 'active', %s, now()) returning id""",
        (user_id, week_start, version),
    ).fetchone()[0]
    for day in payload["days"]:
        day_id = conn.execute(
            """insert into public.workout_plan_days (workout_plan_id, user_id, day_of_week, focus, is_rest)
               values (%s, %s, %s, %s, %s) returning id""",
            (plan_id, user_id, day["day_of_week"], day["focus"], day["is_rest"]),
        ).fetchone()[0]
        for e in day["exercises"]:
            conn.execute(
                """insert into public.workout_plan_exercises
                     (plan_day_id, user_id, exercise_id, position, sets, reps_min, reps_max, rest_sec, target_load_note)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (day_id, user_id, ids[e["exercise_key"]], e["position"], e["sets"], e["reps_min"], e["reps_max"],
                 e["rest_sec"], e["note"]),
            )
    return plan_id
