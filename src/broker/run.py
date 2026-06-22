"""
Robinhood connector CLI.

Single pass (one evaluate->order cycle):
    python -m src.broker.run --symbol SPY --base-quantity 2

Continuous loop every N seconds (e.g. align to your bar interval):
    python -m src.broker.run --symbol SPY --loop 300

Dry run (no real orders — logs intended orders only):
    python -m src.broker.run --symbol SPY --dry-run

Credentials come from the environment (loaded from .env if python-dotenv is
present): ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD, ROBINHOOD_MFA (TOTP secret or
current code).
"""

from __future__ import annotations

import argparse
import logging
import time

from .client import BrokerError, RobinhoodClient
from .trader import LiveTrader, TraderConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
log = logging.getLogger("broker.run")


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass  # optional


def main(argv=None) -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(description="Robinhood connector (Module 5)")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--interval", default="5minute")
    p.add_argument("--base-quantity", type=int, default=1)
    p.add_argument("--params", default="output/active_params.json")
    p.add_argument("--risk", default="output/risk_state.json")
    p.add_argument("--executions", default="output/executions.csv")
    p.add_argument("--allow-short", action="store_true",
                   help="permit short positions (default: long-only, short signal -> flat)")
    p.add_argument("--dry-run", action="store_true",
                   help="log intended orders without placing them")
    p.add_argument("--loop", type=int, default=0,
                   help="seconds between cycles; 0 = run once and exit")
    a = p.parse_args(argv)

    client = RobinhoodClient(dry_run=a.dry_run)
    try:
        client.login()
    except BrokerError as exc:
        log.error("%s", exc)
        return 2

    cfg = TraderConfig(
        symbol=a.symbol, interval=a.interval, base_quantity=a.base_quantity,
        params_path=a.params, risk_path=a.risk, executions_path=a.executions,
        allow_short=a.allow_short,
    )
    trader = LiveTrader(client=client, cfg=cfg)

    def one_cycle() -> None:
        try:
            summary = trader.step()
            log.info("cycle: desired=%s target=%s current=%s delta=%s",
                     summary["desired_position"], summary["target_shares"],
                     summary["current_shares"], summary["delta"])
        except Exception as exc:
            log.exception("cycle failed: %s", exc)

    if a.loop <= 0:
        one_cycle()
        return 0

    log.info("Looping every %ds (Ctrl-C to stop)…", a.loop)
    try:
        while True:
            one_cycle()
            time.sleep(a.loop)
    except KeyboardInterrupt:
        log.info("stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
