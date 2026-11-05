"""Dates in the user's calendar. All users are in India for now, so 'today' means India time."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

INDIA = ZoneInfo("Asia/Kolkata")


def india_today() -> date:
    return datetime.now(INDIA).date()
