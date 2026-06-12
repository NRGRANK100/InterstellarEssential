"""
Pipeline orchestrator — chain the four Interstellar Essential modules.

    1. Optimizer  ->  output/active_params.json   (champion + leaderboard)
    2. Generator  ->  output/<Class>.cs            (NinjaScript from champion)
    3. Risk       ->  output/risk_state.json       (risk_multiplier)
    4. Monitoring ->  Strategy-of-the-Week report  (+ optional daily/audit)

Each stage is independent and writes a file the next stage (or NinjaTrader)
reads, so a failure in one stage is isolated and reported rather than crashing
the whole run. Stages can be skipped individually for partial runs.

Examples
--------
    # full weekly run on free yfinance data, console report
    python run_pipeline.py --symbol SPY --interval 5m --total-trials 500000

    # quick smoke run (tiny budget) to prove the chain end to end
    python run_pipeline.py --total-trials 200 --eval-days 10

    # re-tune + regenerate only (skip risk/report)
    python run_pipeline.py --skip-risk --skip-report
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
log = logging.getLogger("pipeline")


def _stage_optimizer(args) -> bool:
    from src.optimizer.sunday_optimizer import OptimizerConfig, run

    cfg = OptimizerConfig(
        source=args.source,
        symbol=args.symbol,
        interval=args.interval,
        period=args.period,
        csv_path=args.csv_path,
        total_trials=args.total_trials,
        eval_days=args.eval_days,
        max_workers=args.max_workers,
        out_path=args.params,
    )
    payload = run(cfg)
    champ = payload["champion"]
    log.info("Optimizer champion: %s (score=%.4f)", champ["strategy"], champ["score"])
    return True


def _stage_generator(args) -> bool:
    from src.generator.generate import generate

    out = generate(
        params_path=args.params,
        out_dir=args.out_dir,
        param_file=args.nt_param_file,
        risk_file=args.nt_risk_file,
        base_quantity=args.base_quantity,
    )
    log.info("Generated NinjaScript -> %s", out)
    return True


def _stage_risk(args) -> bool:
    from src.risk.engine import RiskConfig, run as risk_run

    cfg = RiskConfig(
        fmp_api_key=args.fmp_key or os.getenv("FMP_API_KEY"),
        news_window_minutes=args.news_window,
        currencies=args.currencies,
        max_daily_drawdown=args.max_daily_drawdown,
        news_source=args.news_source,
        account_state_path=args.account_state,
        out_path=args.risk_out,
    )
    payload = risk_run(cfg)
    log.info("Risk multiplier: %.2f (%s)",
             payload.get("risk_multiplier", 1.0),
             ", ".join(payload.get("reasons", [])) or "no triggers")
    return True


def _stage_report(args) -> bool:
    from src.monitoring.notifier import make_notifier
    from src.monitoring.reports import strategy_of_the_week

    text = strategy_of_the_week(args.params)
    notifier = make_notifier(args.notifier)
    notifier.send(text)
    log.info("Strategy-of-the-Week report sent via %s notifier", args.notifier)
    return True


STAGES = [
    ("optimizer", "skip_optimizer", _stage_optimizer),
    ("generator", "skip_generator", _stage_generator),
    ("risk", "skip_risk", _stage_risk),
    ("report", "skip_report", _stage_report),
]


def run_pipeline(args) -> int:
    os.makedirs(args.out_dir, exist_ok=True)
    failures = []
    for name, skip_attr, fn in STAGES:
        if getattr(args, skip_attr):
            log.info("→ skipping %s stage", name)
            continue
        log.info("→ %s stage starting…", name)
        try:
            fn(args)
        except Exception as exc:  # isolate stage failures
            log.exception("%s stage failed: %s", name, exc)
            failures.append(name)
            if not args.keep_going:
                log.error("Aborting (use --keep-going to run remaining stages).")
                return 1

    if failures:
        log.error("Pipeline finished with failures in: %s", ", ".join(failures))
        return 1
    log.info("Pipeline complete.")
    return 0


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Interstellar Essential pipeline orchestrator")

    # data / optimizer
    p.add_argument("--source", choices=["yfinance", "ninjatrader"], default="yfinance")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--interval", default="5m")
    p.add_argument("--period", default="60d")
    p.add_argument("--csv-path", default=None)
    p.add_argument("--total-trials", type=int, default=500_000)
    p.add_argument("--eval-days", type=int, default=30)
    p.add_argument("--max-workers", type=int, default=None)

    # shared artifacts
    p.add_argument("--out-dir", default="output")
    p.add_argument("--params", default="output/active_params.json")
    p.add_argument("--risk-out", default="output/risk_state.json")

    # generator (paths the live NinjaScript reads on the trading box)
    p.add_argument("--nt-param-file", default=None,
                   help="path the generated .cs reads at runtime (NT Custom folder)")
    p.add_argument("--nt-risk-file", default=None)
    p.add_argument("--base-quantity", type=int, default=1)

    # risk
    p.add_argument("--fmp-key", default=None)
    p.add_argument("--news-source", choices=["fmp", "forexfactory"], default="fmp")
    p.add_argument("--news-window", type=int, default=60)
    p.add_argument("--currencies", nargs="+", default=["USD"])
    p.add_argument("--max-daily-drawdown", type=float, default=0.0)
    p.add_argument("--account-state", default=None,
                   help="JSON file with day_pnl / max_daily_drawdown from the live side")

    # report
    p.add_argument("--notifier", choices=["console", "discord", "telegram"], default="console")

    # stage toggles
    p.add_argument("--skip-optimizer", action="store_true")
    p.add_argument("--skip-generator", action="store_true")
    p.add_argument("--skip-risk", action="store_true")
    p.add_argument("--skip-report", action="store_true")
    p.add_argument("--keep-going", action="store_true",
                   help="continue running later stages even if one fails")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(run_pipeline(_parse_args()))
