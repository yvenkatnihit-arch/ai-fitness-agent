"""What the plan proposal endpoints return."""

from datetime import date, datetime

from pydantic import BaseModel


class ProposalOut(BaseModel):
    id: str
    type: str          # workout_change | meal_change | profile_change | weekly_adjustment
    source: str
    summary: str       # one line for the card
    status: str        # pending | approved | rejected | expired
    created_at: datetime
    payload: dict      # the exact change; for workouts: days -> exercises with sets, reps, rest


def to_proposal_out(row: tuple) -> ProposalOut:
    """Row order is app.db.proposals.PROPOSAL_COLUMNS."""
    return ProposalOut(id=str(row[0]), type=row[1], source=row[2], summary=row[3], status=row[4],
                       payload=row[5], created_at=row[6])


class ProposalListOut(BaseModel):
    proposals: list[ProposalOut]


class PlanExerciseOut(BaseModel):
    position: int
    exercise_key: str
    name: str
    sets: int
    reps_min: int
    reps_max: int
    rest_sec: int
    note: str | None
    form_cues: list[str]


class PlanDayOut(BaseModel):
    day_of_week: int   # 1 = Monday
    focus: str | None
    is_rest: bool
    minutes: int | None   # about how long the day takes (None on a rest day)
    exercises: list[PlanExerciseOut]


class ActivePlanOut(BaseModel):
    id: str
    week_start: date
    version: int
    approved_at: datetime
    days: list[PlanDayOut]
