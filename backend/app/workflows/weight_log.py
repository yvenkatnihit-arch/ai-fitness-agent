"""The weight log (Step 8.6, D-112): record a weigh-in, read the history and its trend.

A weigh-in is a record, not a recalculation: it does NOT change the daily targets (those change when the person edits their weight in
Settings, D-069), but it DOES move the goal-date forecast, which always starts from the latest weight. For a user who must not see numbers
(eating-disorder history, `focus_on_habits`) no weights are shown, and logging is refused with a friendly message."""

from datetime import date, timedelta
from uuid import UUID

from app.calc.weight_trend import summarize
from app.core.time import india_today
from app.db import targets as targets_repo
from app.db import weight as repo
from app.db.transactions import user_transaction
from app.schemas.weight import PointOut, WeightOut

BACKFILL_DAYS = 60
DEFAULT_DAYS = 90
HIDDEN_MESSAGE = "Your plan focuses on regular, balanced meals, so weights are not tracked here."


class WeightRefused(Exception):
    """Something the person can fix. str(e) is safe to show."""


def _hidden(conn) -> bool:
    row = targets_repo.current_targets(conn)
    return bool(row[6]) if row else False            # focus_on_habits


def _out(conn, days: int, today: date) -> WeightOut:
    if _hidden(conn):
        return WeightOut(numbers_hidden=True, entries=[])
    start, target = repo.goal_weights(conn)
    s = summarize(repo.list_entries(conn, today - timedelta(days=days)), start, target)
    return WeightOut(numbers_hidden=False, entries=[PointOut(date=d, weight_kg=kg) for d, kg in s.entries], latest_kg=s.latest_kg, latest_on=s.latest_on,
                     start_weight_kg=s.start_weight_kg, target_weight_kg=s.target_weight_kg, change_since_start_kg=s.change_since_start_kg,
                     kg_to_target=s.kg_to_target, percent_to_target=s.percent_to_target, weekly_change_kg=s.weekly_change_kg)


def read(user_id: UUID, days: int = DEFAULT_DAYS, today: date | None = None) -> WeightOut:
    today = today or india_today()
    with user_transaction(user_id) as conn:
        return _out(conn, days, today)


def record(user_id: UUID, weight_kg: float, measured_on: date | None = None, today: date | None = None) -> WeightOut:
    today = today or india_today()
    day = measured_on or today
    if day > today:
        raise WeightRefused("You can't log a weight for a future date.")
    if day < today - timedelta(days=BACKFILL_DAYS):
        raise WeightRefused(f"You can log a weight for today and the last {BACKFILL_DAYS} days.")
    with user_transaction(user_id) as conn:
        if _hidden(conn):
            raise WeightRefused(HIDDEN_MESSAGE)
        repo.upsert_entry(conn, day, weight_kg)
        return _out(conn, DEFAULT_DAYS, today)


def remove(user_id: UUID, measured_on: date) -> bool:
    with user_transaction(user_id) as conn:
        if _hidden(conn):
            raise WeightRefused(HIDDEN_MESSAGE)
        return repo.delete_entry(conn, measured_on)
