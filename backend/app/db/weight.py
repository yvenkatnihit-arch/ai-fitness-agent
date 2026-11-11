"""Body weight entries as the signed-in user (RLS: only their own rows). One entry per day: a second weigh-in the same day replaces the first."""

from datetime import date

from psycopg import Connection


def upsert_entry(conn: Connection, measured_on: date, weight_kg: float) -> None:
    conn.execute(
        """insert into public.body_weight_entries (user_id, measured_on, weight_kg) values (auth.uid(), %s, %s)
           on conflict (user_id, measured_on) do update set weight_kg = excluded.weight_kg""", (measured_on, weight_kg))


def list_entries(conn: Connection, since: date) -> list[tuple[date, float]]:
    return [(r[0], float(r[1])) for r in conn.execute(
        "select measured_on, weight_kg from public.body_weight_entries where measured_on >= %s order by measured_on", (since,)).fetchall()]


def delete_entry(conn: Connection, measured_on: date) -> bool:
    return conn.execute("delete from public.body_weight_entries where measured_on = %s returning 1", (measured_on,)).fetchone() is not None


def goal_weights(conn: Connection) -> tuple[float | None, float | None]:
    """(start weight, target weight) of the active goal; None where not set."""
    row = conn.execute("select start_weight_kg, target_weight_kg from public.goals where user_id = auth.uid() and active").fetchone()
    return (float(row[0]) if row and row[0] is not None else None, float(row[1]) if row and row[1] is not None else None)
