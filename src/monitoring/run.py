"""
Run — CLI orchestrator for Module 4 (Monitoring System).

Spec mapping
------------
Glue that builds report text (daily / weekly / audit) and dispatches it through
a pluggable notifier.  Mirrors the logging/CLI style of
``src/optimizer/sunday_optimizer.py``.

Examples
--------
    python -m src.monitoring.run --daily --executions output/executions.csv
    python -m src.monitoring.run --weekly --notifier discord
    python -m src.monitoring.run --audit --expected exp.json --actual fills.csv
"""
from __future__ import annotations

import argparse
import logging

from .audit import audit_executions, audit_report
from .notifier import make_notifier
from .reports import daily_report, strategy_of_the_week
from .trade_log import load_executions_csv, load_trades_json

logger = logging.getLogger("monitoring.run")


def _load_trades(path: str):
    """Load trades from CSV (.csv) or JSON (anything else)."""
    if path.lower().endswith(".csv"):
        return load_executions_csv(path)
    return load_trades_json(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interstellar Essential monitoring (Module 4).")
    parser.add_argument("--daily", action="store_true", help="Build and send the daily report.")
    parser.add_argument("--weekly", action="store_true", help="Send Strategy of the Week.")
    parser.add_argument("--audit", action="store_true", help="Run an execution audit.")
    parser.add_argument("--executions", help="Executions file for --daily (CSV or JSON).")
    parser.add_argument("--expected", help="Expected backtest trades for --audit (CSV or JSON).")
    parser.add_argument("--actual", help="Actual broker executions for --audit (CSV or JSON).")
    parser.add_argument(
        "--active-params",
        default="output/active_params.json",
        help="Path to active_params.json for --weekly.",
    )
    parser.add_argument(
        "--notifier",
        choices=["console", "discord", "telegram"],
        default="console",
        help="Notification channel (default: console).",
    )
    return parser


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    notifier = make_notifier(args.notifier)

    if not (args.daily or args.weekly or args.audit):
        logger.error("Nothing to do: pass one of --daily / --weekly / --audit.")
        return 2

    if args.daily:
        if not args.executions:
            logger.error("--daily requires --executions.")
            return 2
        trades = _load_trades(args.executions)
        text = daily_report(trades)
        logger.info("Sending daily report (%d trades).", len(trades))
        notifier.send(text)

    if args.weekly:
        text = strategy_of_the_week(args.active_params)
        logger.info("Sending Strategy of the Week.")
        notifier.send(text)

    if args.audit:
        if not (args.expected and args.actual):
            logger.error("--audit requires --expected and --actual.")
            return 2
        expected = _load_trades(args.expected)
        actual = _load_trades(args.actual)
        result = audit_executions(expected, actual)
        text = audit_report(result)
        logger.info(
            "Audit complete: %d flagged, %d missing, %d extra.",
            result["num_flagged"],
            result["num_missing"],
            result["num_extra"],
        )
        notifier.send(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
