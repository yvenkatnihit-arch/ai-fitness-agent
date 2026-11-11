"""Reading a weight history (Step 8.6, D-112). Pure Python: every number the weight card and the chat show is worked out here, never by
a model or the browser. A trend is information, not a verdict: nothing here judges whether a change is good or bad for someone's health."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

MIN_DAYS_FOR_WEEKLY_RATE = 7      # a weekly rate from less than a week of weigh-ins would be noise
CLOSE_ENOUGH_KG = 0.5             # within this of the target counts as there (same as the forecast)


@dataclass(frozen=True)
class WeightSummary:
    entries: list[tuple[date, float]]          # oldest first
    latest_kg: float | None
    latest_on: date | None
    start_weight_kg: float | None              # the weight when the goal started
    target_weight_kg: float | None
    change_since_start_kg: float | None        # latest minus start (negative = lost)
    kg_to_target: float | None                 # target minus latest (negative = still above the target)
    percent_to_target: int | None              # how much of the way from start to target (0 to 100)
    weekly_change_kg: float | None             # across the entries shown, per week (negative = losing)


def summarize(entries: Sequence[tuple[date, float]], start_weight_kg: float | None, target_weight_kg: float | None) -> WeightSummary:
    """`entries` in any order. Returns rounded numbers ready to show."""
    ordered = sorted((d, float(kg)) for d, kg in entries)
    if not ordered:
        return WeightSummary([], None, None, start_weight_kg, target_weight_kg, None, None, None, None)
    latest_on, latest = ordered[-1]
    first_on, first = ordered[0]
    change = round(latest - start_weight_kg, 1) if start_weight_kg is not None else None
    to_target = round(target_weight_kg - latest, 1) if target_weight_kg is not None else None
    percent = None
    if start_weight_kg is not None and target_weight_kg is not None and abs(start_weight_kg - target_weight_kg) >= CLOSE_ENOUGH_KG:
        done = (start_weight_kg - latest) / (start_weight_kg - target_weight_kg)       # 1 = at the target, negative = moved the wrong way
        percent = max(0, min(100, round(done * 100)))
    span = (latest_on - first_on).days
    weekly = round((latest - first) / span * 7, 2) if span >= MIN_DAYS_FOR_WEEKLY_RATE else None
    return WeightSummary([(d, round(kg, 1)) for d, kg in ordered], round(latest, 1), latest_on,
                         round(start_weight_kg, 1) if start_weight_kg is not None else None,
                         round(target_weight_kg, 1) if target_weight_kg is not None else None, change, to_target, percent, weekly)
