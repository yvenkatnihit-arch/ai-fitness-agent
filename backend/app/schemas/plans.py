"""What the plan proposal endpoints return."""

from datetime import datetime

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
