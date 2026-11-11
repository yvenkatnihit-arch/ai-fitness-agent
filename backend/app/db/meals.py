"""Meal logs, as the signed-in user (RLS: only their own rows). user_id always comes from auth.uid()."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from psycopg import Connection

from app.calc.portions import Nutrition, Per100g


@dataclass(frozen=True)
class LoggableFood:
    id: int
    name: str
    per_100g: Per100g
    unit_grams: dict[str, float]


@dataclass(frozen=True)
class NewItem:
    food_id: int
    quantity: float
    unit: str
    grams: float
    nutrition: Nutrition


def foods_for_logging(conn: Connection, food_ids: list[int]) -> dict[int, LoggableFood]:
    """Values per 100 g and household units for these foods. Missing ids are simply absent."""
    rows = conn.execute(
        """select id, name, kcal_per_100g, protein_g_per_100g, carbs_g_per_100g, fat_g_per_100g
           from public.foods where id = any(%s)""", (food_ids,)).fetchall()
    units: dict[int, dict[str, float]] = {}
    for food_id, unit, grams in conn.execute(
            "select food_id, unit, grams from public.food_units where food_id = any(%s)", (food_ids,)):
        units.setdefault(food_id, {})[unit] = float(grams)
    return {r[0]: LoggableFood(r[0], r[1], Per100g(*(float(v) for v in r[2:6])), units.get(r[0], {}))
            for r in rows}


def insert_meal(conn: Connection, logged_on: date, slot: str, source: str, items: list[NewItem], user_id: UUID | None = None) -> UUID:
    """As the signed-in user (user_id None: auth.uid()), or, for an approved chat proposal applied on the admin connection, for the named user."""
    meal_id = conn.execute(
        """insert into public.meal_logs (user_id, logged_on, slot, source)
           values (coalesce(%s, auth.uid()), %s, %s, %s) returning id""", (user_id, logged_on, slot, source)).fetchone()[0]
    for item in items:
        n = item.nutrition
        conn.execute(
            """insert into public.meal_log_items
                 (meal_log_id, user_id, food_id, quantity, unit, grams, kcal, protein_g, carbs_g, fat_g,
                  match_confidence)
               values (%s, coalesce(%s, auth.uid()), %s, %s, %s, %s, %s, %s, %s, %s, 1.0)""",  # 1.0: picked from a list
            (meal_id, user_id, item.food_id, item.quantity, item.unit, item.grams, n.kcal, n.protein_g, n.carbs_g, n.fat_g))
    return meal_id


def meals_on(conn: Connection, day: date) -> list[dict]:
    """The user's meals for one day, oldest first, each with its items (stored snapshots, not recomputed)."""
    rows = conn.execute(
        """select m.id, m.logged_on, m.slot, m.source, i.id, i.food_id, f.name, i.quantity, i.unit, i.grams,
                  i.kcal, i.protein_g, i.carbs_g, i.fat_g
           from public.meal_logs m
           join public.meal_log_items i on i.meal_log_id = m.id
           join public.foods f on f.id = i.food_id
           where m.logged_on = %s
           order by m.created_at, i.id""", (day,)).fetchall()
    meals: dict[UUID, dict] = {}
    for r in rows:
        meal = meals.setdefault(r[0], {"id": r[0], "logged_on": r[1], "slot": r[2], "source": r[3], "items": []})
        meal["items"].append({
            "id": r[4], "food_id": r[5], "food_name": r[6], "quantity": float(r[7]), "unit": r[8],
            "grams": float(r[9]), "kcal": float(r[10]), "protein_g": float(r[11]), "carbs_g": float(r[12]),
            "fat_g": float(r[13]),
        })
    return list(meals.values())


def daily_totals(conn: Connection, start: date, end: date) -> dict[date, dict[str, float]]:
    """Calories and macros per day for the days between start and end (inclusive) that have at least one logged item. RLS: only the caller's logs."""
    rows = conn.execute(
        """select m.logged_on, sum(i.kcal), sum(i.protein_g), sum(i.carbs_g), sum(i.fat_g)
           from public.meal_logs m join public.meal_log_items i on i.meal_log_id = m.id
           where m.logged_on between %s and %s group by m.logged_on""", (start, end)).fetchall()
    return {r[0]: {"kcal": float(r[1]), "protein_g": float(r[2]), "carbs_g": float(r[3]), "fat_g": float(r[4])} for r in rows}


def delete_meal(conn: Connection, meal_id: UUID) -> bool:
    """True if a meal was deleted. Someone else's meal is invisible under RLS, so it reads as 'not found'."""
    return conn.execute("delete from public.meal_logs where id = %s returning id", (meal_id,)).fetchone() is not None
