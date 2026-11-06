"""Reading what the split recommender needs, and saving the user's choice (as the signed-in user, under RLS)."""

from dataclasses import dataclass

from psycopg import Connection


@dataclass(frozen=True)
class SplitInputs:
    days_per_week: int
    level: str
    goal: str
    chosen_key: str | None = None   # the split they picked earlier, if any


def read_split_inputs(conn: Connection) -> SplitInputs | None:
    """Days per week and level from the Training step, the active goal, and any split already chosen.
    None until the training answers and the goal are saved."""
    row = conn.execute(
        """select p.days_per_week, p.experience_level, g.goal_type, p.split_key
           from public.profiles p
           join public.goals g on g.user_id = p.id and g.active
           where p.id = auth.uid()"""
    ).fetchone()
    if row is None or None in row[:3]:
        return None
    return SplitInputs(int(row[0]), row[1], row[2], row[3])


def save_split_choice(conn: Connection, split_key: str) -> None:
    conn.execute("update public.profiles set split_key = %s where id = auth.uid()", (split_key,))
