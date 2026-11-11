"""Which weekday a person means (Step 7.12a, D-103). Plain code: the model passes a NAME ("monday", "today"), never a date or a number,
so it never does date arithmetic. Plans number days 1 = Monday ... 7 = Sunday (the database's day_of_week)."""

from datetime import date, timedelta
from typing import Literal

DAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DayName = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "today", "tomorrow", "yesterday"]


def resolve_day(name: str, today: date) -> int:
    """1 to 7 for a weekday name, or for today, tomorrow or yesterday relative to `today` (the user's own calendar date)."""
    key = name.strip().lower()
    if key == "today":
        return today.isoweekday()
    if key == "tomorrow":
        return (today + timedelta(days=1)).isoweekday()
    if key == "yesterday":
        return (today - timedelta(days=1)).isoweekday()
    if key not in DAY_NAMES:
        raise ValueError(f"unknown day: {name!r}")
    return DAY_NAMES.index(key) + 1


def day_name(day_of_week: int) -> str:
    return DAY_NAMES[day_of_week - 1].capitalize()
