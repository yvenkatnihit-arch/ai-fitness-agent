"""Reading the inputs for the calculation engine, and saving / reading calculated targets."""

import json
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from psycopg import Connection

from app.calc.engine import Targets
from app.safety.safety_config import SCREENING_FLAGS


@dataclass(frozen=True)
class SavedInputs:
    goal_id: UUID
    goal_type: str
    weight_kg: float
    height_cm: float
    date_of_birth: date
    sex: str
    activity_level: str
    pace: str
    flags: frozenset[str]


def read_inputs(conn: Connection) -> SavedInputs | None:
    """As the user (RLS): everything calculate_targets() needs. None if something is missing."""
    flag_columns = ", ".join(f"s.{name}" for name in SCREENING_FLAGS)
    row = conn.execute(
        f"""select g.id, g.goal_type,
                   (select w.weight_kg from public.body_weight_entries w
                     where w.user_id = p.id order by w.measured_on desc limit 1),
                   p.height_cm, p.date_of_birth, p.sex, p.activity_level, g.pace, {flag_columns}
            from public.profiles p
            join public.goals g on g.user_id = p.id and g.active
            join public.health_screening s on s.user_id = p.id
            where p.id = auth.uid()"""
    ).fetchone()
    if row is None or None in row[:8]:
        return None
    flags = frozenset(name for name, value in zip(SCREENING_FLAGS, row[8:]) if value)
    return SavedInputs(row[0], row[1], float(row[2]), float(row[3]), row[4], row[5], row[6], row[7], flags)


def mark_onboarded(admin_conn: Connection, user_id: UUID) -> bool:
    """Admin: set onboarded_at once. False if it was already set (e.g. a double-tap)."""
    return admin_conn.execute(
        "update public.profiles set onboarded_at = now() where id = %s and onboarded_at is null returning id",
        (user_id,),
    ).fetchone() is not None


def insert_targets(admin_conn: Connection, user_id: UUID, goal_id: UUID, t: Targets, inputs: dict) -> None:
    """Admin: calculated_targets is server-written (D-027)."""
    admin_conn.execute(
        """insert into public.calculated_targets
             (user_id, goal_id, bmr_kcal, tdee_kcal, goal_target_kcal, calorie_target_kcal,
              protein_g, fat_g, carbs_g, reasons, doctor_note, focus_on_habits, inputs)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (user_id, goal_id, t.bmr_kcal, t.tdee_kcal, t.goal_target_kcal, t.calorie_target_kcal,
         t.protein_g, t.fat_g, t.carbs_g, list(t.reasons), t.doctor_note, t.focus_on_habits,
         json.dumps(inputs)),
    )


def current_targets(conn: Connection):
    """As the user (RLS): the newest targets row, or None."""
    return conn.execute(
        """select calorie_target_kcal, protein_g, fat_g, carbs_g, reasons, doctor_note, focus_on_habits
           from public.calculated_targets
           where user_id = auth.uid()
           order by effective_from desc limit 1"""
    ).fetchone()
