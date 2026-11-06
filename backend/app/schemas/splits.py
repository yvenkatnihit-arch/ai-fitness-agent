"""What the split recommendation endpoint returns."""

from pydantic import BaseModel, ConfigDict, Field

from app.calc.splits import Recommendation


class SplitDayOut(BaseModel):
    label: str
    muscles: list[str]
    patterns: list[str]   # the movement patterns the plan will pick exercises for


class RecommendationOut(BaseModel):
    key: str              # saved when the user picks this split
    name: str
    summary: str
    fit: str              # best | good | possible
    training_days: int
    recovery_days: int    # easy days on top (1 when you ask for 7 days)
    muscle_frequency: int
    reasons: list[str]
    cautions: list[str]
    schedule: list[SplitDayOut]


class SplitRecommendationsOut(BaseModel):
    days_per_week: int
    level: str
    goal: str
    chosen_key: str | None   # the split the user picked, while it still fits their days
    recommendations: list[RecommendationOut]


class SplitChoiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    split_key: str = Field(min_length=3, max_length=40, pattern=r"^[a-z0-9_]+$")


class SplitChoiceOut(BaseModel):
    split_key: str


def to_recommendation_out(rec: Recommendation) -> RecommendationOut:
    split = rec.split
    return RecommendationOut(
        key=split.key, name=split.name, summary=split.summary, fit=rec.fit, training_days=split.training_days,
        recovery_days=rec.recovery_days, muscle_frequency=split.muscle_frequency,
        reasons=list(rec.reasons), cautions=list(rec.cautions),
        schedule=[SplitDayOut(label=d.label, muscles=list(d.muscles), patterns=list(d.patterns)) for d in split.days],
    )
