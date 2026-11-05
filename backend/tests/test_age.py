from datetime import date

import pytest

from app.calc.age import age_on


@pytest.mark.parametrize(
    ("born", "on", "expected"),
    [
        (date(2000, 6, 15), date(2026, 6, 14), 25),  # day before birthday
        (date(2000, 6, 15), date(2026, 6, 15), 26),  # on the birthday
        (date(2000, 2, 29), date(2026, 2, 28), 25),  # leap-day birthday, non-leap year: not yet
        (date(2000, 2, 29), date(2026, 3, 1), 26),
        (date(2000, 2, 29), date(2028, 2, 29), 28),  # leap year: birthday exists
        (date(2026, 11, 5), date(2026, 11, 5), 0),   # born today
    ],
)
def test_age_on(born, on, expected):
    assert age_on(born, on) == expected


def test_future_birth_date_is_rejected():
    with pytest.raises(ValueError):
        age_on(date(2030, 1, 1), date(2026, 11, 5))
