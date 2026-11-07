"""Onboarding reads and writes. Every function takes a connection from user_transaction(),
so all SQL runs as the signed-in user under RLS and `auth.uid()` is that user."""

from datetime import date

from psycopg import Connection

from app.schemas.onboarding import BasicsIn, GoalIn, PreferencesIn, ScreeningIn, TrainingIn
from app.schemas.onboarding_status import OnboardingStatus

STEPS = ("consent", "basics", "goal", "preferences", "training", "screening")


class OnboardingError(Exception):
    """A step was attempted out of order. The message is safe to show the user."""


class NotConsented(OnboardingError):
    def __init__(self):
        super().__init__("Please accept the privacy notice first.")


class BasicsMissing(OnboardingError):
    def __init__(self):
        super().__init__("Please fill in your basic details first.")


class AlreadyOnboarded(OnboardingError):
    def __init__(self):
        super().__init__("Onboarding is already complete. You can change your details in Settings.")


STATUS_SQL = """
    select
      p.consent_at is not null,
      p.date_of_birth is not null and p.sex is not null and p.height_cm is not null
        and p.activity_level is not null
        and exists (select 1 from public.body_weight_entries w where w.user_id = p.id),
      exists (select 1 from public.goals g where g.user_id = p.id and g.active),
      p.diet_type is not null,
      p.experience_level is not null and p.workout_location is not null and p.days_per_week is not null,
      exists (select 1 from public.health_screening s where s.user_id = p.id),
      p.onboarded_at is not null
    from public.profiles p
    where p.id = auth.uid()
"""


def get_status(conn: Connection) -> OnboardingStatus:
    row = conn.execute(STATUS_SQL).fetchone()
    done = dict(zip((*STEPS, "completed"), row or (False,) * 7))
    if done["completed"]:
        next_step = "done"
    else:
        next_step = next((step for step in STEPS if not done[step]), "complete")
    return OnboardingStatus(**done, next_step=next_step)


def _require_open(conn: Connection) -> None:
    """Consent given and onboarding not finished yet."""
    row = conn.execute(
        "select consent_at is not null, onboarded_at is not null from public.profiles where id = auth.uid()"
    ).fetchone()
    if row is None or not row[0]:
        raise NotConsented()
    if row[1]:
        raise AlreadyOnboarded()


def save_consent(conn: Connection, notice_version: str) -> None:
    """Create the profile row on first consent; later consents record the newer notice."""
    row = conn.execute("select onboarded_at is not null from public.profiles where id = auth.uid()").fetchone()
    if row and row[0]:
        raise AlreadyOnboarded()
    conn.execute(
        """insert into public.profiles (id, consent_at, consent_version)
           values (auth.uid(), now(), %s)
           on conflict (id) do update
             set consent_at = excluded.consent_at, consent_version = excluded.consent_version""",
        (notice_version,),
    )


def save_basics(conn: Connection, basics: BasicsIn, today: date) -> None:
    _require_open(conn)
    conn.execute(
        """update public.profiles
           set display_name = %s, date_of_birth = %s, sex = %s, height_cm = %s, activity_level = %s
           where id = auth.uid()""",
        (basics.display_name, basics.date_of_birth, basics.sex, basics.height_cm, basics.activity_level),
    )
    # The onboarding weight is today's weigh-in (one per day; saving again replaces it).
    conn.execute(
        """insert into public.body_weight_entries (user_id, measured_on, weight_kg)
           values (auth.uid(), %s, %s)
           on conflict (user_id, measured_on) do update set weight_kg = excluded.weight_kg""",
        (today, basics.weight_kg),
    )


def latest_weight_kg(conn: Connection) -> float | None:
    row = conn.execute(
        """select weight_kg from public.body_weight_entries
           where user_id = auth.uid() order by measured_on desc limit 1"""
    ).fetchone()
    return float(row[0]) if row else None


def save_goal(conn: Connection, goal: GoalIn, start_weight_kg: float, today: date) -> None:
    """Keep exactly one active goal: update it if it exists, otherwise create it."""
    _require_open(conn)
    params = (goal.goal_type, goal.target_weight_kg, start_weight_kg, today, goal.pace)
    updated = conn.execute(
        """update public.goals
           set goal_type = %s, target_weight_kg = %s, start_weight_kg = %s, started_on = %s, pace = %s
           where user_id = auth.uid() and active""",
        params,
    ).rowcount
    if updated == 0:
        conn.execute(
            """insert into public.goals (user_id, goal_type, target_weight_kg, start_weight_kg, started_on, pace)
               values (auth.uid(), %s, %s, %s, %s, %s)""",
            params,
        )


def save_preferences(conn: Connection, prefs: PreferencesIn) -> None:
    _require_open(conn)
    conn.execute(
        "update public.profiles set diet_type = %s, cuisine = %s, disliked_foods = %s where id = auth.uid()",
        (prefs.diet_type, prefs.cuisine, prefs.disliked_foods),
    )


def save_training(conn: Connection, training: TrainingIn) -> None:
    _require_open(conn)
    conn.execute(
        """update public.profiles
           set experience_level = %s, workout_location = %s, equipment = %s, days_per_week = %s,
               session_minutes = %s
           where id = auth.uid()""",
        (training.experience_level, training.workout_location, training.equipment, training.days_per_week,
         training.session_minutes),
    )


def save_screening(conn: Connection, s: ScreeningIn) -> None:
    _require_open(conn)
    conn.execute(
        """insert into public.health_screening
             (user_id, pregnant_or_breastfeeding, diabetes, heart_or_bp, kidney,
              recent_surgery_or_injury, eating_disorder_history, injury_areas)
           values (auth.uid(), %s, %s, %s, %s, %s, %s, %s)
           on conflict (user_id) do update set
             pregnant_or_breastfeeding = excluded.pregnant_or_breastfeeding,
             diabetes = excluded.diabetes,
             heart_or_bp = excluded.heart_or_bp,
             kidney = excluded.kidney,
             recent_surgery_or_injury = excluded.recent_surgery_or_injury,
             eating_disorder_history = excluded.eating_disorder_history,
             injury_areas = excluded.injury_areas""",
        (s.pregnant_or_breastfeeding, s.diabetes, s.heart_or_bp, s.kidney,
         s.recent_surgery_or_injury, s.eating_disorder_history, s.injury_areas),
    )
