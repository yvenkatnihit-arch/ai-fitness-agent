"""Shared input checks for calc functions."""

import math


def require_number(name: str, value: object) -> float:
    """Raise ValueError unless value is a finite int or float (bool is rejected)."""
    # bool is a subclass of int in Python, so reject it explicitly (True would pass as 1).
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a number, got {value!r}")
    return value


def require_range(name: str, value: object, low: float, high: float) -> float:
    """Raise ValueError unless value is a number between low and high (inclusive)."""
    number = require_number(name, value)
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}, got {number}")
    return number


def require_positive(name: str, value: object) -> float:
    """Raise ValueError unless value is a number greater than zero."""
    number = require_number(name, value)
    if number <= 0:
        raise ValueError(f"{name} must be positive, got {number}")
    return number
