"""Age in whole years on a given day."""

from datetime import date


def age_on(date_of_birth: date, on: date) -> int:
    """Completed years. Someone born on 29 Feb turns a year older on 1 Mar in non-leap years."""
    if date_of_birth > on:
        raise ValueError("date_of_birth is in the future")
    had_birthday = (on.month, on.day) >= (date_of_birth.month, date_of_birth.day)
    return on.year - date_of_birth.year - (0 if had_birthday else 1)
