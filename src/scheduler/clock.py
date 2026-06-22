"""
Market clock + schedule predicates (pure, testable — no I/O, no sleeping).

All decisions the daemon makes about *when* to act live here so they can be
unit-tested by passing in a fixed `now`. Times are US/Eastern, the timezone of
the US equity session, with a simple regular-hours model (09:30–16:00, Mon–Fri).
US market holidays are not enumerated; a holiday simply produces a no-trade day
because either the broker rejects orders or no fills occur — the daemon treats
that gracefully rather than maintaining a holiday calendar.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def now_et() -> datetime:
    """Current wall-clock time in US/Eastern."""
    return datetime.now(ET)


def to_et(dt: datetime) -> datetime:
    """Coerce any datetime to US/Eastern (assume ET if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ET)
    return dt.astimezone(ET)


def is_weekday(dt: datetime) -> bool:
    return to_et(dt).weekday() < 5  # Mon..Fri == 0..4


def is_market_open(dt: datetime) -> bool:
    """True during regular US equity hours (Mon–Fri, 09:30–16:00 ET)."""
    d = to_et(dt)
    return is_weekday(d) and MARKET_OPEN <= d.time() < MARKET_CLOSE


def minutes_since_open(dt: datetime) -> float:
    d = to_et(dt)
    open_dt = d.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute,
                        second=0, microsecond=0)
    return (d - open_dt).total_seconds() / 60.0


def is_due(last_run: datetime | None, now: datetime, interval_minutes: float) -> bool:
    """Generic 'has `interval_minutes` elapsed since `last_run`?' predicate."""
    if last_run is None:
        return True
    return (to_et(now) - to_et(last_run)) >= timedelta(minutes=interval_minutes)


def is_weekly_due(
    last_run: datetime | None,
    now: datetime,
    weekday: int,
    at: time,
) -> bool:
    """
    True if the weekly optimize job should fire.

    Fires once per calendar week on/after `weekday` at/after time `at` (ET),
    and won't fire again until the next week. `weekday`: Mon=0 .. Sun=6.
    """
    d = to_et(now)
    # only consider firing on the target weekday once we're past `at`
    reached = (d.weekday() == weekday and d.time() >= at) or d.weekday() > weekday
    if not reached:
        # earlier in the week than the trigger; only fire if we somehow never
        # ran and we're already at/after the weekday+time
        return False
    if last_run is None:
        return True
    last = to_et(last_run)
    return _week_key(d) != _week_key(last)


def is_daily_report_due(
    last_run: datetime | None,
    now: datetime,
    after: time,
) -> bool:
    """True once per weekday at/after `after` (ET), e.g. just past the close."""
    d = to_et(now)
    if not is_weekday(d) or d.time() < after:
        return False
    if last_run is None:
        return True
    last = to_et(last_run)
    return last.date() != d.date()


def _week_key(dt: datetime) -> tuple[int, int]:
    iso = dt.isocalendar()
    return (iso.year, iso.week)
