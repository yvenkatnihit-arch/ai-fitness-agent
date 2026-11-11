"""Step 7.11e (D-100): the chat rate limit decision, offline (pure function, fixed clock)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core import chat_limits as cl

NOW = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
ago = lambda *seconds: [NOW - timedelta(seconds=s) for s in seconds]   # noqa: E731
TEN_MIN_FIVE = ((600, 5),)


def test_under_the_limit_is_allowed_and_nothing_is_not_limited():
    assert cl.seconds_to_wait([], NOW) is None
    assert cl.seconds_to_wait(ago(10, 20, 30, 40), NOW, TEN_MIN_FIVE) is None            # 4 of 5


def test_at_the_limit_the_wait_is_until_the_oldest_needed_message_leaves_the_window():
    assert cl.seconds_to_wait(ago(500, 400, 300, 200, 100), NOW, TEN_MIN_FIVE) == 100     # 5 of 5: the 500 s old one leaves in 100 s
    assert cl.seconds_to_wait(ago(590, 400, 300, 200, 100), NOW, TEN_MIN_FIVE) == 10


def test_over_the_limit_waits_for_enough_messages_to_leave_not_just_the_oldest():
    times = ago(590, 580, 570, 560, 550, 540, 530)                                        # 7 messages, limit 5: three must leave
    assert cl.seconds_to_wait(times, NOW, TEN_MIN_FIVE) == 600 - 570                      # the 3rd oldest (570 s ago) leaves in 30 s


def test_messages_outside_the_window_and_future_times_do_not_count():
    assert cl.seconds_to_wait(ago(601, 700, 800, 900, 1000, 2000), NOW, TEN_MIN_FIVE) is None
    assert cl.seconds_to_wait([NOW + timedelta(seconds=5)] * 9, NOW, TEN_MIN_FIVE) is None


def test_the_longest_full_window_decides():
    windows = ((600, 3), (3600, 4))
    assert cl.seconds_to_wait(ago(3000, 2000, 100, 50), NOW, windows) == 3600 - 3000      # 10 min: 2 of 3 (fine); hour: 4 of 4 (full)
    # 10 min: 4 of 3 (the 90 s old one must leave: 510 s); hour: 4 of 4 (the 100 s old one must leave: 3500 s). The longer wait wins.
    assert cl.seconds_to_wait(ago(100, 90, 80, 70), NOW, windows) == 3500
    assert cl.seconds_to_wait(ago(3300, 100, 90, 80), NOW, windows) == 500                # hour: 4 of 4 frees in 300 s; 10 min: 3 of 3 frees in 500 s (the 100 s old one leaves); the longer wins


def test_the_wait_is_never_zero_or_fractional():
    wait = cl.seconds_to_wait([NOW - timedelta(seconds=599.7)] * 5, NOW, TEN_MIN_FIVE)
    assert wait == 1 and isinstance(wait, int)


def test_the_real_limits_are_sensible():
    assert cl.WINDOWS == ((600, 15), (86400, 150)) and cl.LOOKBACK_SECONDS == 86400
    assert cl.seconds_to_wait(ago(*range(1, 15)), NOW) is None                            # 14 in 10 minutes is fine
    assert cl.seconds_to_wait(ago(*range(1, 16)), NOW) is not None                        # the 16th is not


@pytest.mark.parametrize("wait, text", [(30, "30 seconds"), (300, "5 minutes"), (7200, "2 hours")])
def test_the_message_says_how_long_in_plain_words(wait, text):
    assert text in cl.friendly_message(wait)
