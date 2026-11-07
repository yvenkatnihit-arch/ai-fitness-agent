"""Reading the exercise library and the user's training details (as the signed-in user, under RLS)."""

from dataclasses import dataclass

from psycopg import Connection

from app.calc.exercise_filter import ExerciseOption


@dataclass(frozen=True)
class TrainingContext:
    level: str
    workout_location: str
    equipment: frozenset[str]
    injuries: frozenset[str]
    session_minutes: int | None = None   # null for accounts made before the question
    focus_areas: tuple[str, ...] = ()    # muscles to bring up, at most two


def read_training_context(conn: Connection) -> TrainingContext | None:
    """Level, place, equipment and injuries from onboarding. None when onboarding has not saved them yet:
    without the injury answers we must not guess that the user has none."""
    row = conn.execute(
        """select p.experience_level, p.workout_location, p.equipment, s.injury_areas, p.session_minutes, p.focus_areas
           from public.profiles p
           left join public.health_screening s on s.user_id = p.id
           where p.id = auth.uid()"""
    ).fetchone()
    if row is None or row[0] is None or row[1] is None or row[3] is None:
        return None
    return TrainingContext(row[0], row[1], frozenset(row[2]), frozenset(row[3]), row[4], tuple(row[5]))


def list_exercises(conn: Connection) -> list[ExerciseOption]:
    rows = conn.execute(
        """select id, key, name, muscle_groups, equipment, location, difficulty, movement_pattern,
                  form_cues, contraindications, review_status
           from public.exercises order by name"""
    ).fetchall()
    return [
        ExerciseOption(id=r[0], key=r[1], name=r[2], muscle_groups=tuple(r[3]), equipment=tuple(r[4]),
                       location=r[5], difficulty=r[6], movement_pattern=r[7], form_cues=tuple(r[8].split("\n")),
                       contraindications=tuple(r[9]), review_status=r[10])
        for r in rows
    ]
