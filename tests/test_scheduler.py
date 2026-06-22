"""
Network-free tests for the Scheduler (Module 6).

Covers the pure clock predicates and the daemon's due/tick logic with injected
job functions (no broker, no sleeping, fixed `now`). Same style as the others.

Run:  python tests/test_scheduler.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scheduler import clock                                  # noqa: E402
from src.scheduler.daemon import Scheduler, SchedulerConfig, RunState  # noqa: E402

ET = ZoneInfo("America/New_York")


def _et(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ET)


# ── clock: market hours ──────────────────────────────────────────────────


def test_market_open_on_weekday_midday():
    # Wed 2026-06-17, 11:00 ET
    assert clock.is_market_open(_et(2026, 6, 17, 11, 0)) is True


def test_market_closed_before_open_and_after_close():
    assert clock.is_market_open(_et(2026, 6, 17, 9, 0)) is False    # pre-open
    assert clock.is_market_open(_et(2026, 6, 17, 16, 30)) is False  # post-close


def test_market_closed_on_weekend():
    # Sat 2026-06-20
    assert clock.is_market_open(_et(2026, 6, 20, 12, 0)) is False


# ── clock: interval / weekly / daily predicates ─────────────────────────


def test_is_due_interval():
    last = _et(2026, 6, 17, 10, 0)
    assert clock.is_due(last, _et(2026, 6, 17, 10, 4), 5) is False
    assert clock.is_due(last, _et(2026, 6, 17, 10, 5), 5) is True
    assert clock.is_due(None, _et(2026, 6, 17, 10, 0), 5) is True


def test_weekly_due_fires_once_per_week():
    # Sunday weekday=6 at 08:00
    sun_before = _et(2026, 6, 21, 7, 0)   # Sun pre-trigger
    sun_after = _et(2026, 6, 21, 9, 0)    # Sun post-trigger
    assert clock.is_weekly_due(None, sun_before, 6, time(8, 0)) is False
    assert clock.is_weekly_due(None, sun_after, 6, time(8, 0)) is True
    # already ran this week -> not due again same week
    assert clock.is_weekly_due(sun_after, _et(2026, 6, 21, 12, 0), 6, time(8, 0)) is False
    # next week -> due again
    assert clock.is_weekly_due(sun_after, _et(2026, 6, 28, 9, 0), 6, time(8, 0)) is True


def test_daily_report_due_once_per_day_after_close():
    after = time(16, 5)
    assert clock.is_daily_report_due(None, _et(2026, 6, 17, 16, 0), after) is False
    assert clock.is_daily_report_due(None, _et(2026, 6, 17, 16, 10), after) is True
    ran = _et(2026, 6, 17, 16, 10)
    assert clock.is_daily_report_due(ran, _et(2026, 6, 17, 17, 0), after) is False
    assert clock.is_daily_report_due(ran, _et(2026, 6, 18, 16, 10), after) is True


# ── daemon: due_jobs / tick with injected jobs ───────────────────────────


def _scheduler(tmp, **over):
    calls = {"weekly": 0, "trade": 0, "report": 0}

    def mk(name):
        def fn(now):
            calls[name] += 1
        return fn

    cfg = SchedulerConfig(
        state_path=str(Path(tmp) / "state.json"),
        trade_every_minutes=5, weekly_weekday=6, weekly_at=time(8, 0),
        report_after=time(16, 5), **over,
    )
    s = Scheduler(cfg=cfg, weekly_fn=mk("weekly"), trade_fn=mk("trade"),
                  report_fn=mk("report"))
    return s, calls


def test_trade_only_during_market_hours():
    with tempfile.TemporaryDirectory() as tmp:
        s, calls = _scheduler(tmp)
        # Wed midday -> trade is due (fresh state)
        ran = s.tick(_et(2026, 6, 17, 11, 0))
        assert "trade" in ran and calls["trade"] == 1
    with tempfile.TemporaryDirectory() as tmp2:
        # fresh state dir: pre-open on a weekday -> no trade
        s2, calls2 = _scheduler(tmp2)
        ran2 = s2.tick(_et(2026, 6, 17, 8, 0))  # before open
        assert "trade" not in ran2


def test_trade_respects_interval():
    with tempfile.TemporaryDirectory() as tmp:
        s, calls = _scheduler(tmp)
        s.tick(_et(2026, 6, 17, 11, 0))          # fires
        s.tick(_et(2026, 6, 17, 11, 3))          # 3 min later -> too soon
        assert calls["trade"] == 1
        s.tick(_et(2026, 6, 17, 11, 6))          # 6 min later -> fires again
        assert calls["trade"] == 2


def test_weekly_and_report_fire_and_persist():
    with tempfile.TemporaryDirectory() as tmp:
        s, calls = _scheduler(tmp)
        # Sunday 09:00 ET -> weekly due (market closed, so no trade)
        ran = s.tick(_et(2026, 6, 21, 9, 0))
        assert "weekly" in ran and "trade" not in ran
        # state persisted -> a fresh Scheduler sees last_weekly and won't refire
        s2, calls2 = _scheduler(tmp)
        ran2 = s2.tick(_et(2026, 6, 21, 12, 0))
        assert "weekly" not in ran2

        # report after close on a weekday
        s3, calls3 = _scheduler(tmp)
        ran3 = s3.tick(_et(2026, 6, 17, 16, 10))
        assert "report" in ran3


def test_failing_job_does_not_crash_tick():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = SchedulerConfig(state_path=str(Path(tmp) / "s.json"),
                              trade_every_minutes=5)

        def boom(now):
            raise RuntimeError("broker down")

        ok = {"n": 0}

        def fine(now):
            ok["n"] += 1

        s = Scheduler(cfg=cfg, weekly_fn=fine, trade_fn=boom, report_fn=fine)
        # midday: trade is due but raises; tick must swallow it and not mark it
        ran = s.tick(_et(2026, 6, 17, 11, 0))
        assert "trade" not in ran            # failed job not recorded as ran
        assert s.state.last_trade is None     # so it can retry next tick


def test_run_once_forces_job():
    with tempfile.TemporaryDirectory() as tmp:
        s, calls = _scheduler(tmp)
        # Saturday (market closed) but --once trade should still force it
        s.run_once("trade")
        assert calls["trade"] == 1


def test_runstate_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "state.json")
        st = RunState(last_trade=_et(2026, 6, 17, 11, 0))
        st.save(path)
        loaded = RunState.load(path)
        assert loaded.last_trade == st.last_trade
        assert loaded.last_weekly is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")
