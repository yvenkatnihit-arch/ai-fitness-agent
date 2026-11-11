"""How many chat messages one user may send (Step 7.11e, D-100). A cost and quota guard, not a safety limit: every message can start
several model calls, and our Gemini quota is shared by all users.

Counted from the saved chat messages (the database), so the limit survives restarts and holds across several servers. The decision
is a pure function of the message times, so it is unit-tested without a database or a clock."""

from collections.abc import Sequence
from datetime import datetime
from math import ceil

# (window in seconds, most messages allowed in that window). Tune here only.
WINDOWS: tuple[tuple[int, int], ...] = ((10 * 60, 15), (24 * 60 * 60, 150))
LOOKBACK_SECONDS = max(w for w, _ in WINDOWS)


def seconds_to_wait(sent_at: Sequence[datetime], now: datetime, windows: Sequence[tuple[int, int]] | None = None) -> int | None:
    """None when another message is allowed now; otherwise how many whole seconds until it will be (the longest of the windows
    that are full). `sent_at` = the times of the user's earlier messages, any order."""
    wait = 0.0
    for seconds, most in (WINDOWS if windows is None else windows):
        inside = sorted(t for t in sent_at if 0 <= (now - t).total_seconds() < seconds)
        if len(inside) >= most:
            # Once the (n - most + 1)-th oldest message leaves the window, one slot is free.
            wait = max(wait, seconds - (now - inside[len(inside) - most]).total_seconds())
    return max(1, ceil(wait)) if wait > 0 else None


def friendly_message(wait: int) -> str:
    if wait < 90:
        return f"You are sending messages very quickly. Please wait about {wait} seconds and try again."
    if wait < 5400:
        return f"You have reached the chat limit for now. Please try again in about {ceil(wait / 60)} minutes."
    return f"You have reached today's chat limit. Please try again in about {ceil(wait / 3600)} hours."
