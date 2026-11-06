"""What the goal-date forecast shows. The wording lives here; the dates come from app/calc/forecast.py."""

from datetime import date

from pydantic import BaseModel

from app.calc.forecast import Forecast

ESTIMATE_NOTE = (
    "This is an estimate. It assumes you follow your plan 70 to 100 percent of the time, and it is "
    "recalculated as your weight changes."
)


class ForecastOut(BaseModel):
    status: str
    message: str
    current_weight_kg: float | None
    target_weight_kg: float | None
    weekly_change_kg: float | None   # negative = losing; this week, if the plan is followed fully
    earliest: date | None
    likely: date | None
    latest: date | None
    weeks_likely: int | None
    note: str | None                 # the "this is an estimate" line, only when there are dates


def _message(f: Forecast) -> str:
    match f.status:
        case "ready":
            return f"At this pace you could reach {f.target_weight_kg:g} kg around {f.likely:%d %b %Y}."
        case "no_target":
            return "Set a target weight to see a goal date. (Goals like general fitness and recomposition don't aim at a body weight.)"
        case "wrong_direction":
            return "Your target weight is in the opposite direction from your goal. Update it to see a date."
        case "already_there":
            return "You are already at your target weight."
        case "not_moving":
            return "Within safe limits your plan doesn't move your weight toward this target, so there is no date to predict."
        case "too_far":
            return "At a safe pace this target is more than two years away. A closer first target may be easier to stay with."
        case "habits_only":
            return "Your plan focuses on healthy habits, not on dates or weights."
    raise ValueError(f"unknown forecast status {f.status!r}")


def to_forecast_out(f: Forecast) -> ForecastOut:
    hide_numbers = f.status == "habits_only"   # no weights at all for eating-disorder history
    return ForecastOut(
        status=f.status, message=_message(f),
        current_weight_kg=None if hide_numbers else round(f.current_weight_kg, 1),
        target_weight_kg=None if hide_numbers else f.target_weight_kg,
        weekly_change_kg=None if hide_numbers else f.weekly_change_kg,
        earliest=f.earliest, likely=f.likely, latest=f.latest, weeks_likely=f.weeks_likely,
        note=ESTIMATE_NOTE if f.status == "ready" else None,
    )
