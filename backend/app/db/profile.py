"""Reading and editing a finished profile (as the signed-in user, under RLS). Every function takes a connection from
user_transaction(), so `auth.uid()` is that user. Onboarding's own saves are in app/db/onboarding.py."""

from datetime import date
from typing import Any

from psycopg import Connection

from app.calc.profile_edit import SCREENING_FLAGS
from app.schemas.onboarding import BasicsIn, GoalIn, PreferencesIn, ScreeningIn, TrainingIn


def read_profile(conn: Connection) -> dict[str, dict[str, Any]] | None:
    """The user's answers by onboarding section, or None until onboarding is finished."""
    row = conn.execute(
        """select display_name, date_of_birth, sex, height_cm, activity_level, experience_level, workout_location,
                  equipment, days_per_week, session_minutes, diet_type, cuisine, disliked_foods, onboarded_at
           from public.profiles where id = auth.uid()"""
    ).fetchone()
    if row is None or row[13] is None:
        return None
    weight = conn.execute(
        "select weight_kg from public.body_weight_entries where user_id = auth.uid() order by measured_on desc limit 1"
    ).fetchone()
    goal = conn.execute(
        "select goal_type, target_weight_kg, pace from public.goals where user_id = auth.uid() and active"
    ).fetchone()
    screening = conn.execute(
        f"select {', '.join(SCREENING_FLAGS)}, injury_areas from public.health_screening where user_id = auth.uid()"
    ).fetchone()
    if weight is None or goal is None or screening is None:
        return None
    return {
        "basics": {"display_name": row[0], "date_of_birth": row[1], "sex": row[2], "height_cm": float(row[3]),
                   "weight_kg": float(weight[0]), "activity_level": row[4]},
        "goal": {"goal_type": goal[0], "target_weight_kg": float(goal[1]) if goal[1] is not None else None, "pace": goal[2]},
        "preferences": {"diet_type": row[10], "cuisine": row[11], "disliked_foods": list(row[12] or [])},
        "training": {"experience_level": row[5], "workout_location": row[6], "equipment": list(row[7] or []),
                     "days_per_week": row[8], "session_minutes": row[9]},
        "screening": {**dict(zip(SCREENING_FLAGS, map(bool, screening[:6]))), "injury_areas": list(screening[6] or [])},
    }


def update_basics(conn: Connection, basics: BasicsIn, weight_changed: bool, today: date) -> None:
    conn.execute(
        """update public.profiles
           set display_name = %s, date_of_birth = %s, sex = %s, height_cm = %s, activity_level = %s
           where id = auth.uid()""",
        (basics.display_name, basics.date_of_birth, basics.sex, basics.height_cm, basics.activity_level),
    )
    if weight_changed:   # a new weight is today's weigh-in (one per day, history kept); an untouched weight adds nothing
        conn.execute(
            """insert into public.body_weight_entries (user_id, measured_on, weight_kg)
               values (auth.uid(), %s, %s)
               on conflict (user_id, measured_on) do update set weight_kg = excluded.weight_kg""",
            (today, basics.weight_kg),
        )


def update_goal(conn: Connection, goal: GoalIn, latest_weight_kg: float, today: date) -> None:
    """Same goal type: change the target and pace in place (keeps the start weight and date for progress). A NEW goal
    type closes the old goal and starts a new one from today's weight, so earlier progress is not rewritten."""
    current = conn.execute("select id, goal_type from public.goals where user_id = auth.uid() and active").fetchone()
    if current is not None and current[1] == goal.goal_type:
        conn.execute("update public.goals set target_weight_kg = %s, pace = %s where id = %s",
                     (goal.target_weight_kg, goal.pace, current[0]))
        return
    if current is not None:
        conn.execute("update public.goals set active = false where id = %s", (current[0],))
    conn.execute(
        """insert into public.goals (user_id, goal_type, target_weight_kg, start_weight_kg, started_on, pace)
           values (auth.uid(), %s, %s, %s, %s, %s)""",
        (goal.goal_type, goal.target_weight_kg, latest_weight_kg, today, goal.pace),
    )


def update_preferences(conn: Connection, prefs: PreferencesIn) -> None:
    conn.execute(
        "update public.profiles set diet_type = %s, cuisine = %s, disliked_foods = %s where id = auth.uid()",
        (prefs.diet_type, prefs.cuisine, prefs.disliked_foods),
    )


def update_training(conn: Connection, training: TrainingIn) -> None:
    conn.execute(
        """update public.profiles
           set experience_level = %s, workout_location = %s, equipment = %s, days_per_week = %s, session_minutes = %s
           where id = auth.uid()""",
        (training.experience_level, training.workout_location, training.equipment, training.days_per_week,
         training.session_minutes),
    )


def update_screening(conn: Connection, s: ScreeningIn) -> None:
    conn.execute(
        f"""update public.health_screening set
              {', '.join(f'{flag} = %s' for flag in SCREENING_FLAGS)}, injury_areas = %s
            where user_id = auth.uid()""",
        (*(getattr(s, flag) for flag in SCREENING_FLAGS), s.injury_areas),
    )
