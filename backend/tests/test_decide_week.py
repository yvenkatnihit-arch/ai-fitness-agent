"""Which Monday an approved plan starts on."""

from datetime import date

import pytest

from app.workflows.decide_proposal import effective_week_start

MON = date(2026, 11, 9)


@pytest.mark.parametrize("planned,today,expected", [
    (MON, date(2026, 11, 6), MON),                     # approved before the start: keep it
    (MON, date(2026, 11, 9), MON),                     # approved on the Monday itself
    (MON, date(2026, 11, 12), MON),                    # approved mid-week of the planned week: still this week
    (MON, date(2026, 11, 15), MON),                    # Sunday of the planned week
    (MON, date(2026, 11, 16), date(2026, 11, 16)),     # the planned week is over, today is the next Monday
    (MON, date(2026, 11, 18), date(2026, 11, 23)),     # approved late: start on the coming Monday
])
def test_effective_week_start(planned, today, expected):
    assert effective_week_start(planned, today) == expected and expected.weekday() == 0
