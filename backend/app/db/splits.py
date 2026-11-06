"""Reading what the split recommender needs (as the signed-in user, under RLS)."""

from dataclasses import dataclass

from psycopg import Connection


@dataclass(frozen=True)
class SplitInputs:
    days_per_week: int
    level: str
    goal: str


def read_split_inputs(conn: Connection) -> SplitInputs | None:
    """Days per week and level from the Training step, and the active goal. None until those are saved."""
    row = conn.execute(
        """select p.days_per_week, p.experience_level, g.goal_type
           from public.profiles p
           join public.goals g on g.user_id = p.id and g.active
           where p.id = auth.uid()"""
    ).fetchone()
    if row is None or None in row:
        return None
    return SplitInputs(int(row[0]), row[1], row[2])
