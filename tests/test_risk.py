"""
Smoke + correctness tests for the Risk Layer (Module 3).

These run entirely offline — events and PnL are injected directly, so no
network call ever happens (the FMP / ForexFactory fetchers are not exercised).

Run:  python -m pytest tests/ -q     (or just `python tests/test_risk.py`)
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.risk.news import (  # noqa: E402
    IMPACT_HIGH,
    IMPACT_MEDIUM,
    NewsEvent,
    has_high_impact_news,
)
from src.risk.drawdown import within_drawdown_buffer  # noqa: E402
from src.risk.engine import RiskConfig, evaluate, write_risk_state  # noqa: E402


NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)

# The exact regex the generated NinjaScript uses to read the multiplier.
_TEMPLATE_REGEX = re.compile(r'"risk_multiplier"\s*:\s*([0-9]*\.?[0-9]+)')


def _high_event(minutes_from_now: float, currency: str = "USD") -> NewsEvent:
    return NewsEvent(
        title="CPI",
        currency=currency,
        impact=IMPACT_HIGH,
        datetime_utc=NOW + timedelta(minutes=minutes_from_now),
    )


# ── news ──────────────────────────────────────────────────────────────────


def test_news_inside_window_trips():
    tripped, ev = has_high_impact_news([_high_event(30)], now=NOW, window_minutes=60)
    assert tripped is True
    assert ev is not None and ev.title == "CPI"


def test_news_outside_window_does_not_trip():
    tripped, ev = has_high_impact_news([_high_event(120)], now=NOW, window_minutes=60)
    assert tripped is False
    assert ev is None


def test_news_medium_impact_does_not_trip():
    ev = NewsEvent("PMI", "USD", IMPACT_MEDIUM, NOW)
    tripped, found = has_high_impact_news([ev], now=NOW, window_minutes=60)
    assert tripped is False
    assert found is None


def test_news_currency_filter():
    events = [_high_event(10, currency="EUR")]
    # filtered to USD -> the EUR event is ignored
    tripped, _ = has_high_impact_news(
        events, now=NOW, window_minutes=60, currencies=["USD"]
    )
    assert tripped is False
    # filtered to EUR -> it trips
    tripped, ev = has_high_impact_news(
        events, now=NOW, window_minutes=60, currencies=["EUR"]
    )
    assert tripped is True and ev is not None


# ── drawdown ────────────────────────────────────────────────────────────────


def test_drawdown_at_80pct_trips():
    # loss of 800 against a 1000 limit -> 80% used -> within 20% buffer
    tripped, pct = within_drawdown_buffer(-800.0, 1000.0, buffer_frac=0.20)
    assert tripped is True
    assert abs(pct - 0.8) < 1e-9


def test_drawdown_at_50pct_does_not_trip():
    tripped, pct = within_drawdown_buffer(-500.0, 1000.0, buffer_frac=0.20)
    assert tripped is False
    assert abs(pct - 0.5) < 1e-9


def test_drawdown_nonpositive_limit_returns_false():
    tripped, pct = within_drawdown_buffer(-9999.0, 0.0)
    assert tripped is False
    assert pct == 0.0


def test_drawdown_profit_does_not_trip():
    tripped, pct = within_drawdown_buffer(500.0, 1000.0)
    assert tripped is False
    assert pct == 0.0


# ── engine.evaluate ─────────────────────────────────────────────────────────


def test_evaluate_news_only_is_reduced():
    cfg = RiskConfig(max_daily_drawdown=1000.0)
    payload = evaluate(cfg, events=[_high_event(10)], day_pnl=-100.0, now=NOW)
    assert payload["risk_multiplier"] == 0.5
    assert "high_impact_news" in payload["reasons"]
    assert "drawdown_buffer" not in payload["reasons"]


def test_evaluate_drawdown_only_is_reduced():
    cfg = RiskConfig(max_daily_drawdown=1000.0)
    payload = evaluate(cfg, events=[], day_pnl=-900.0, now=NOW)
    assert payload["risk_multiplier"] == 0.5
    assert "drawdown_buffer" in payload["reasons"]
    assert "high_impact_news" not in payload["reasons"]


def test_evaluate_both_is_reduced():
    cfg = RiskConfig(max_daily_drawdown=1000.0)
    payload = evaluate(cfg, events=[_high_event(5)], day_pnl=-950.0, now=NOW)
    assert payload["risk_multiplier"] == 0.5
    assert "high_impact_news" in payload["reasons"]
    assert "drawdown_buffer" in payload["reasons"]


def test_evaluate_neither_is_normal():
    cfg = RiskConfig(max_daily_drawdown=1000.0)
    payload = evaluate(cfg, events=[], day_pnl=-100.0, now=NOW)
    assert payload["risk_multiplier"] == 1.0
    assert payload["reasons"] == []


def test_evaluate_payload_has_required_key():
    cfg = RiskConfig(max_daily_drawdown=1000.0)
    payload = evaluate(cfg, events=[], day_pnl=0.0, now=NOW)
    assert "risk_multiplier" in payload
    assert "reasons" in payload
    assert "generated_at" in payload


# ── write_risk_state ────────────────────────────────────────────────────────


def test_write_risk_state_roundtrip():
    cfg = RiskConfig(max_daily_drawdown=1000.0)
    payload = evaluate(cfg, events=[_high_event(5)], day_pnl=0.0, now=NOW)
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "risk_state.json")
        write_risk_state(payload, path)
        text = Path(path).read_text(encoding="utf-8")
        loaded = json.loads(text)
        assert "risk_multiplier" in loaded
        assert loaded["risk_multiplier"] == 0.5
        # the value must match the NinjaScript template regex
        m = _TEMPLATE_REGEX.search(text)
        assert m is not None
        assert float(m.group(1)) == 0.5


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")
