"""Writing an approved meal plan (admin: the plan tables are server-written, D-027).

Every function takes an admin connection, which BYPASSES row level security, so each one filters by user_id itself.
Callers run them inside ONE admin_transaction so the whole approval is all-or-nothing.
"""

from collections.abc import Sequence
from datetime import date
from typing import NamedTuple
from uuid import UUID

from psycopg import Connection


class ItemRow(NamedTuple):
    day_of_week: int
    slot: str
    position: int
    food_id: int
    grams: float
    unit: str | None
    quantity: float | None
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


def latest_targets_id(conn: Connection, user_id: UUID) -> UUID | None:
    row = conn.execute(
        "select id from public.calculated_targets where user_id = %s order by effective_from desc limit 1", (user_id,)
    ).fetchone()
    return row[0] if row else None


def activate_meal_plan(conn: Connection, user_id: UUID, week_start: date, rows: Sequence[ItemRow],
                       targets_id: UUID | None) -> UUID:
    """Archive the user's active meal plan, then write this one as the active plan. Returns the new plan id."""
    conn.execute("update public.meal_plans set status = 'archived' where user_id = %s and status = 'active'", (user_id,))
    version = conn.execute(
        "select coalesce(max(version), 0) + 1 from public.meal_plans where user_id = %s and week_start = %s",
        (user_id, week_start),
    ).fetchone()[0]
    plan_id = conn.execute(
        """insert into public.meal_plans (user_id, week_start, status, version, targets_id, approved_at)
           values (%s, %s, 'active', %s, %s, now()) returning id""",
        (user_id, week_start, version, targets_id),
    ).fetchone()[0]
    for r in rows:
        conn.execute(
            """insert into public.meal_plan_items
                 (meal_plan_id, user_id, day_of_week, slot, position, food_id, grams, household_unit, household_qty,
                  kcal, protein_g, carbs_g, fat_g)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (plan_id, user_id, *r),
        )
    return plan_id
