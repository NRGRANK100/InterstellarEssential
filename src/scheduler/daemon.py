"""
The scheduler daemon — one loop that runs the whole pipeline automatically.

See package docstring for the high-level design. This module is the wiring:
config, persistent run-state, the three jobs, and the tick loop.

The jobs reuse the existing modules unchanged:
  weekly  -> src.optimizer + src.generator + src.risk   (via run_pipeline stages)
  trade   -> src.risk (refresh) + src.broker.LiveTrader.step
  report  -> src.monitoring (daily_report over today's executions)
"""

from __future__ import annotations

import json
import logging
import os
import time as _time
from dataclasses import asdict, dataclass, field
from datetime import datetime, time as dtime
from pathlib import Path

from . import clock

log = logging.getLogger("scheduler")


# ── config & state ───────────────────────────────────────────────────────


@dataclass
class SchedulerConfig:
    symbol: str = "SPY"
    interval: str = "5m"               # optimizer interval (mapped for RH)
    broker_interval: str = "5minute"   # robin_stocks interval for live signal
    base_quantity: int = 1
    source: str = "robinhood"          # data feed for the weekly re-tune
    total_trials: int = 500_000
    eval_days: int = 30

    # cadence
    trade_every_minutes: float = 5.0
    weekly_weekday: int = 6            # Sunday (Mon=0 .. Sun=6)
    weekly_at: dtime = dtime(8, 0)     # 08:00 ET
    report_after: dtime = dtime(16, 5)  # just past the close
    tick_seconds: float = 30.0

    # behavior
    dry_run: bool = False
    allow_short: bool = False
    trade_in_market_hours_only: bool = True

    # paths
    out_dir: str = "output"
    params_path: str = "output/active_params.json"
    risk_path: str = "output/risk_state.json"
    executions_path: str = "output/executions.csv"
    state_path: str = "output/scheduler_state.json"
    notifier: str = "console"

    # risk inputs
    fmp_key: str | None = None
    news_source: str = "fmp"
    max_daily_drawdown: float = 0.0
    account_state: str | None = None


@dataclass
class RunState:
    last_weekly: datetime | None = None
    last_trade: datetime | None = None
    last_report: datetime | None = None

    def to_json(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in asdict(self).items()}

    @classmethod
    def load(cls, path: str) -> "RunState":
        try:
            data = json.loads(Path(path).read_text())
        except Exception:
            return cls()

        def _dt(v):
            return datetime.fromisoformat(v) if v else None

        return cls(
            last_weekly=_dt(data.get("last_weekly")),
            last_trade=_dt(data.get("last_trade")),
            last_report=_dt(data.get("last_report")),
        )

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = f"{path}.tmp"
        Path(tmp).write_text(json.dumps(self.to_json(), indent=2))
        os.replace(tmp, path)


# ── the scheduler ────────────────────────────────────────────────────────


@dataclass
class Scheduler:
    cfg: SchedulerConfig = field(default_factory=SchedulerConfig)
    # injectable hooks so tests can run jobs without network/broker
    weekly_fn: object = None
    trade_fn: object = None
    report_fn: object = None

    def __post_init__(self):
        self.state = RunState.load(self.cfg.state_path)
        self.weekly_fn = self.weekly_fn or self._job_weekly
        self.trade_fn = self.trade_fn or self._job_trade
        self.report_fn = self.report_fn or self._job_report

    # ── decision: which jobs are due at `now` ───────────────────────────
    def due_jobs(self, now: datetime) -> list[str]:
        jobs: list[str] = []
        if clock.is_weekly_due(self.state.last_weekly, now,
                               self.cfg.weekly_weekday, self.cfg.weekly_at):
            jobs.append("weekly")

        trade_ok = (not self.cfg.trade_in_market_hours_only) or clock.is_market_open(now)
        if trade_ok and clock.is_due(self.state.last_trade, now,
                                     self.cfg.trade_every_minutes):
            jobs.append("trade")

        if clock.is_daily_report_due(self.state.last_report, now, self.cfg.report_after):
            jobs.append("report")
        return jobs

    # ── one evaluation of the schedule (used by the loop and by --once) ─
    def tick(self, now: datetime | None = None) -> list[str]:
        now = now or clock.now_et()
        ran: list[str] = []
        for job in self.due_jobs(now):
            try:
                {"weekly": self.weekly_fn,
                 "trade": self.trade_fn,
                 "report": self.report_fn}[job](now)
                self._mark(job, now)
                ran.append(job)
            except Exception as exc:  # a failing job must not kill the daemon
                log.exception("job %s failed: %s", job, exc)
        if ran:
            self.state.save(self.cfg.state_path)
        return ran

    def _mark(self, job: str, now: datetime) -> None:
        if job == "weekly":
            self.state.last_weekly = now
        elif job == "trade":
            self.state.last_trade = now
        elif job == "report":
            self.state.last_report = now

    # ── the loop ────────────────────────────────────────────────────────
    def run_forever(self) -> None:
        log.info("Scheduler up: symbol=%s dry_run=%s trade_every=%smin tick=%ss",
                 self.cfg.symbol, self.cfg.dry_run,
                 self.cfg.trade_every_minutes, self.cfg.tick_seconds)
        while True:
            ran = self.tick()
            if ran:
                log.info("ran jobs: %s", ", ".join(ran))
            _time.sleep(self.cfg.tick_seconds)

    def run_once(self, job: str) -> list[str]:
        """Force-run a single job now (ignores schedule), e.g. for --once."""
        fn = {"weekly": self.weekly_fn, "trade": self.trade_fn,
              "report": self.report_fn}[job]
        fn(clock.now_et())
        self._mark(job, clock.now_et())
        self.state.save(self.cfg.state_path)
        return [job]

    # ── default job implementations (real pipeline) ─────────────────────
    def _job_weekly(self, now: datetime) -> None:
        log.info("WEEKLY: re-tuning + regenerating + refreshing risk")
        from src.optimizer.sunday_optimizer import OptimizerConfig, run as opt_run

        opt_run(OptimizerConfig(
            source=self.cfg.source, symbol=self.cfg.symbol, interval=self.cfg.interval,
            total_trials=self.cfg.total_trials, eval_days=self.cfg.eval_days,
            out_path=self.cfg.params_path,
        ))
        # regenerate the NinjaScript too (cheap; keeps the NT path in sync)
        try:
            from src.generator.generate import generate
            generate(params_path=self.cfg.params_path, out_dir=self.cfg.out_dir,
                     base_quantity=self.cfg.base_quantity)
        except Exception as exc:
            log.warning("generator step skipped: %s", exc)
        self._refresh_risk(now)

    def _job_trade(self, now: datetime) -> None:
        self._refresh_risk(now)  # make sure the multiplier is current
        from src.broker.client import RobinhoodClient
        from src.broker.trader import LiveTrader, TraderConfig

        client = RobinhoodClient(dry_run=self.cfg.dry_run)
        client.login()
        trader = LiveTrader(client=client, cfg=TraderConfig(
            symbol=self.cfg.symbol, interval=self.cfg.broker_interval,
            base_quantity=self.cfg.base_quantity, params_path=self.cfg.params_path,
            risk_path=self.cfg.risk_path, executions_path=self.cfg.executions_path,
            allow_short=self.cfg.allow_short,
        ))
        summary = trader.step()
        log.info("TRADE: desired=%s target=%s current=%s delta=%s",
                 summary["desired_position"], summary["target_shares"],
                 summary["current_shares"], summary["delta"])

    def _job_report(self, now: datetime) -> None:
        from src.monitoring.notifier import make_notifier
        from src.monitoring.reports import daily_report
        from src.monitoring.trade_log import load_executions_csv

        try:
            trades = load_executions_csv(self.cfg.executions_path)
        except Exception:
            trades = []
        text = daily_report(trades, day=clock.to_et(now).date())
        make_notifier(self.cfg.notifier).send(text)
        log.info("REPORT: daily report sent (%d executions)", len(trades))

    def _refresh_risk(self, now: datetime) -> None:
        from src.risk.engine import RiskConfig, run as risk_run

        risk_run(RiskConfig(
            fmp_api_key=self.cfg.fmp_key or os.getenv("FMP_API_KEY"),
            news_source=self.cfg.news_source, currencies=["USD"],
            max_daily_drawdown=self.cfg.max_daily_drawdown,
            account_state_path=self.cfg.account_state,
            out_path=self.cfg.risk_path,
        ))


# ── CLI ──────────────────────────────────────────────────────────────────


def _build_cfg(a) -> SchedulerConfig:
    return SchedulerConfig(
        symbol=a.symbol, interval=a.interval, broker_interval=a.broker_interval,
        base_quantity=a.base_quantity, source=a.source, total_trials=a.total_trials,
        eval_days=a.eval_days, trade_every_minutes=a.trade_every, tick_seconds=a.tick,
        dry_run=a.dry_run, allow_short=a.allow_short, notifier=a.notifier,
        params_path=a.params, risk_path=a.risk, executions_path=a.executions,
        state_path=a.state, out_dir=a.out_dir, fmp_key=a.fmp_key,
        news_source=a.news_source, max_daily_drawdown=a.max_daily_drawdown,
        account_state=a.account_state,
    )


def main(argv=None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s")
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Interstellar Essential scheduler (auto mode)")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--interval", default="5m")
    p.add_argument("--broker-interval", default="5minute")
    p.add_argument("--base-quantity", type=int, default=1)
    p.add_argument("--source", choices=["yfinance", "robinhood", "ninjatrader"],
                   default="robinhood")
    p.add_argument("--total-trials", type=int, default=500_000)
    p.add_argument("--eval-days", type=int, default=30)
    p.add_argument("--trade-every", type=float, default=5.0, help="minutes between trade cycles")
    p.add_argument("--tick", type=float, default=30.0, help="loop tick seconds")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--allow-short", action="store_true")
    p.add_argument("--notifier", choices=["console", "discord", "telegram"], default="console")
    p.add_argument("--out-dir", default="output")
    p.add_argument("--params", default="output/active_params.json")
    p.add_argument("--risk", default="output/risk_state.json")
    p.add_argument("--executions", default="output/executions.csv")
    p.add_argument("--state", default="output/scheduler_state.json")
    p.add_argument("--fmp-key", default=None)
    p.add_argument("--news-source", choices=["fmp", "forexfactory"], default="fmp")
    p.add_argument("--max-daily-drawdown", type=float, default=0.0)
    p.add_argument("--account-state", default=None)
    p.add_argument("--once", choices=["weekly", "trade", "report"], default=None,
                   help="run a single job now and exit (for testing / manual kicks)")
    a = p.parse_args(argv)

    sched = Scheduler(cfg=_build_cfg(a))
    if a.once:
        ran = sched.run_once(a.once)
        log.info("ran once: %s", ", ".join(ran))
        return 0
    try:
        sched.run_forever()
    except KeyboardInterrupt:
        log.info("scheduler stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
