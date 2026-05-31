"""
Module 3 (Risk Layer): high-impact news detection.

Maps to spec: "Add a news/risk engine using FinancialModelingPrep or
ForexFactory to detect high-impact news. If high-impact news occurs ...
automatically reduce position size by 50%."

This module provides:
  * A ``NewsEvent`` dataclass.
  * Two fetchers (FinancialModelingPrep primary, ForexFactory fallback).
  * ``has_high_impact_news`` -- a pure, testable predicate that decides
    whether a high-impact event falls within a time window of "now".

All network access (``requests``) is imported lazily INSIDE the fetch
functions, so importing this module never requires the network or the
``requests`` package, and any fetch failure degrades gracefully to ``[]``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("interstellar.risk.news")

# FMP economic calendar endpoint.
FMP_ECONOMIC_CALENDAR_URL = "https://financialmodelingprep.com/api/v3/economic_calendar"
# ForexFactory public weekly JSON feed.
FOREXFACTORY_THISWEEK_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Canonical impact levels.
IMPACT_HIGH = "High"
IMPACT_MEDIUM = "Medium"
IMPACT_LOW = "Low"
IMPACT_UNKNOWN = "Unknown"

_HTTP_TIMEOUT = 10


@dataclass
class NewsEvent:
    """A single economic-calendar event."""

    title: str
    currency: str  # currency / country code, e.g. "USD"
    impact: str  # one of IMPACT_HIGH / IMPACT_MEDIUM / IMPACT_LOW / IMPACT_UNKNOWN
    datetime_utc: datetime | None  # event time in UTC (None if unparseable)

    @property
    def is_high_impact(self) -> bool:
        return self.impact == IMPACT_HIGH


def _normalize_impact(raw: Any) -> str:
    """Map a provider's impact string to a canonical impact level."""
    if not raw:
        return IMPACT_UNKNOWN
    text = str(raw).strip().lower()
    if text in ("high", "3"):
        return IMPACT_HIGH
    if text in ("medium", "moderate", "2"):
        return IMPACT_MEDIUM
    if text in ("low", "1"):
        return IMPACT_LOW
    if text in ("holiday", "none", "0"):
        return IMPACT_LOW
    return IMPACT_UNKNOWN


def _parse_dt(raw: Any) -> datetime | None:
    """Best-effort parse of an ISO-ish timestamp into a UTC-aware datetime."""
    if not raw:
        return None
    text = str(raw).strip()
    # Normalize a trailing 'Z' to an explicit offset for fromisoformat.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    candidates = (text, text.replace(" ", "T"))
    for cand in candidates:
        try:
            dt = datetime.fromisoformat(cand)
            break
        except ValueError:
            dt = None
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive timestamps are already UTC.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fetch_fmp_economic_calendar(
    api_key: str,
    from_date: str,
    to_date: str,
    session: Any = None,
) -> list[NewsEvent]:
    """Fetch the FMP economic calendar between ``from_date`` and ``to_date``.

    Dates are ``YYYY-MM-DD`` strings. Returns ``[]`` on any failure so the
    caller can fall back gracefully (defensive: network is lazy/guarded).
    """
    try:
        import requests  # lazy import: module import never needs network deps
    except Exception:  # pragma: no cover - requests usually installed
        logger.warning("requests not available; cannot fetch FMP calendar")
        return []

    params = {"from": from_date, "to": to_date, "apikey": api_key}
    try:
        getter = session.get if session is not None else requests.get
        resp = getter(FMP_ECONOMIC_CALENDAR_URL, params=params, timeout=_HTTP_TIMEOUT)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:  # network / JSON / HTTP errors all degrade to []
        logger.warning("FMP economic calendar fetch failed: %s", exc)
        return []

    events: list[NewsEvent] = []
    for row in rows or []:
        try:
            events.append(
                NewsEvent(
                    title=str(row.get("event") or row.get("title") or ""),
                    currency=str(row.get("currency") or row.get("country") or ""),
                    impact=_normalize_impact(row.get("impact")),
                    datetime_utc=_parse_dt(row.get("date")),
                )
            )
        except Exception:
            continue
    return events


def fetch_forexfactory_calendar(session: Any = None) -> list[NewsEvent]:
    """Fetch the ForexFactory public weekly JSON feed (fallback source).

    Returns ``[]`` on any failure (defensive: network is lazy/guarded).
    """
    try:
        import requests  # lazy import
    except Exception:  # pragma: no cover
        logger.warning("requests not available; cannot fetch ForexFactory calendar")
        return []

    try:
        getter = session.get if session is not None else requests.get
        resp = getter(FOREXFACTORY_THISWEEK_URL, timeout=_HTTP_TIMEOUT)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:
        logger.warning("ForexFactory calendar fetch failed: %s", exc)
        return []

    events: list[NewsEvent] = []
    for row in rows or []:
        try:
            events.append(
                NewsEvent(
                    title=str(row.get("title") or ""),
                    currency=str(row.get("country") or row.get("currency") or ""),
                    impact=_normalize_impact(row.get("impact")),
                    datetime_utc=_parse_dt(row.get("date")),
                )
            )
        except Exception:
            continue
    return events


def has_high_impact_news(
    events: list[NewsEvent],
    now: datetime | None = None,
    window_minutes: int = 60,
    currencies: list[str] | None = None,
) -> tuple[bool, NewsEvent | None]:
    """Return ``(True, event)`` if a High-impact event lies within
    ``+/- window_minutes`` of ``now``, else ``(False, None)``.

    Pure and testable: pass ``events`` in directly. ``currencies`` (if given)
    restricts the check to those currency/country codes (case-insensitive).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    window = timedelta(minutes=window_minutes)
    wanted = {c.upper() for c in currencies} if currencies else None

    for ev in events:
        if not ev.is_high_impact:
            continue
        if wanted is not None and ev.currency.upper() not in wanted:
            continue
        if ev.datetime_utc is None:
            continue
        dt = ev.datetime_utc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if abs(dt - now) <= window:
            return True, ev
    return False, None
