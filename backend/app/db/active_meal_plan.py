"""Reading the user's active meal plan (as the signed-in user, under RLS)."""

from psycopg import Connection


def read_active_meal_plan(conn: Connection) -> dict | None:
    """The active plan, its items (with food names), the user's latest targets and the plan's 'how made' summary."""
    plan = conn.execute(
        "select id, week_start, version, approved_at from public.meal_plans where status = 'active'"
    ).fetchone()
    if plan is None:
        return None
    items = conn.execute(
        """select i.day_of_week, i.slot, i.position, f.name, i.grams, i.household_unit, i.household_qty,
                  i.kcal, i.protein_g, i.carbs_g, i.fat_g
           from public.meal_plan_items i join public.foods f on f.id = i.food_id
           where i.meal_plan_id = %s order by i.day_of_week, i.slot, i.position""",
        (plan[0],),
    ).fetchall()
    targets = conn.execute(
        """select calorie_target_kcal, protein_g, carbs_g, fat_g, focus_on_habits
           from public.calculated_targets where user_id = auth.uid() order by effective_from desc limit 1"""
    ).fetchone()
    made = conn.execute(
        """select payload -> 'how_made' from public.plan_proposals
           where type = 'meal_change' and status = 'approved' order by decided_at desc limit 1"""
    ).fetchone()
    return {"plan": plan, "items": items, "targets": targets, "how_made": made[0] if made else None}
