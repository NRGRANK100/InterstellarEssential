"""
Module 6 — the Scheduler (the "auto" layer).

Turns the pipeline into a hands-off daemon. A single long-running loop wakes on
a fixed tick and fires three time-based jobs, so nothing needs cron:

  * Weekly optimize  — the "Sunday Optimizer": re-tune + regenerate + refresh
    the risk state once a week (default Sunday). Writes active_params.json.
  * Trade cycle      — during market hours, every N minutes: refresh the risk
    state, then run one Robinhood evaluate->order cycle (LiveTrader.step).
  * Daily report     — shortly after the close: build the daily PnL / win-rate
    report from the day's executions and send it via the notifier.

Everything is driven off US/Eastern market time and is idempotent: each job
records the last time it ran (in a small JSON state file) so a restart mid-day
never double-fires a job, and the live trader only ever trades the position
*delta*, so an extra tick can't compound a position.

Run:
    python -m src.scheduler.daemon --symbol SPY --base-quantity 1            # live
    python -m src.scheduler.daemon --symbol SPY --dry-run                    # safe
    python -m src.scheduler.daemon --symbol SPY --once weekly                # one-shot

Safety: live trading is ON unless --dry-run. The daemon refuses to place
real orders outside regular US equity hours.
"""

from __future__ import annotations

from .daemon import SchedulerConfig, Scheduler

__all__ = ["SchedulerConfig", "Scheduler"]
