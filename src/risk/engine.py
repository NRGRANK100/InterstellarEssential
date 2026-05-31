"""
Module 3 (Risk Layer): orchestrator.

Maps to spec: "If high-impact news occurs OR the account reaches within 20% of
max daily drawdown, automatically reduce position size by 50%."

The engine evaluates BOTH conditions and writes ``output/risk_state.json``.
The JSON contains the key ``risk_multiplier`` (a number, ``0.5`` when either
condition trips, else ``1.0``) which the generated NinjaScript reads at session
start via regex (see templates/Strategy.cs.j2).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from src.risk.drawdown import read_account_state, within_drawdown_buffer
from src.risk.news import (
    NewsEvent,
    fetch_fmp_economic_calendar,
    fetch_forexfactory_calendar,
    has_high_impact_news,
)

logger = logging.getLogger("interstellar.risk.engine")


@dataclass
class RiskConfig:
    fmp_api_key: str | None = None
    news_window_minutes: int = 60
    currencies: list[str] = field(default_factory=lambda: ["USD"])
    max_daily_drawdown: float = 0.0
    drawdown_buffer_frac: float = 0.20
    reduced_multiplier: float = 0.5
    normal_multiplier: float = 1.0
    out_path: str = "output/risk_state.json"
    account_state_path: str | None = None
    news_source: str = "fmp"  # "fmp" | "forexfactory"


def _fetch_events(cfg: RiskConfig, now: datetime) -> list[NewsEvent]:
    """Fetch calendar events for the configured source (defensive)."""
    if cfg.news_source == "forexfactory":
        return fetch_forexfactory_calendar()
    if cfg.news_source == "fmp":
        if not cfg.fmp_api_key:
            logger.warning("No FMP API key; skipping FMP news fetch")
            return []
        # Look one day either side of now to comfortably cover the window.
        from_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        to_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        return fetch_fmp_economic_calendar(cfg.fmp_api_key, from_date, to_date)
    logger.warning("Unknown news_source %r; returning no events", cfg.news_source)
    return []


def evaluate(
    cfg: RiskConfig,
    *,
    events: list[NewsEvent] | None = None,
    day_pnl: float | None = None,
    max_daily_drawdown: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate both risk conditions and return the full payload dict.

    If ``events`` or ``day_pnl`` are not supplied, they are fetched/read
    defensively. The result always contains ``risk_multiplier``.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # --- News condition ---------------------------------------------------
    if events is None:
        events = _fetch_events(cfg, now)
    news_tripped, next_event = has_high_impact_news(
        events,
        now=now,
        window_minutes=cfg.news_window_minutes,
        currencies=cfg.currencies,
    )

    # --- Drawdown condition ----------------------------------------------
    # Resolve account numbers: explicit args > account_state file > config.
    if max_daily_drawdown is None:
        max_daily_drawdown = cfg.max_daily_drawdown
    if (day_pnl is None or max_daily_drawdown in (None, 0.0)) and cfg.account_state_path:
        state = read_account_state(cfg.account_state_path)
        if day_pnl is None:
            day_pnl = state.get("day_pnl")
        if not max_daily_drawdown:
            max_daily_drawdown = state.get("max_daily_drawdown", cfg.max_daily_drawdown)

    dd_day_pnl = 0.0 if day_pnl is None else float(day_pnl)
    dd_limit = 0.0 if max_daily_drawdown is None else float(max_daily_drawdown)
    dd_tripped, pct_used = within_drawdown_buffer(
        dd_day_pnl, dd_limit, buffer_frac=cfg.drawdown_buffer_frac
    )

    # --- Combine ----------------------------------------------------------
    reasons: list[str] = []
    if news_tripped:
        reasons.append("high_impact_news")
    if dd_tripped:
        reasons.append("drawdown_buffer")

    tripped = news_tripped or dd_tripped
    multiplier = cfg.reduced_multiplier if tripped else cfg.normal_multiplier

    next_event_info: dict[str, Any] | None = None
    if next_event is not None:
        next_event_info = {
            "title": next_event.title,
            "currency": next_event.currency,
            "impact": next_event.impact,
            "datetime_utc": (
                next_event.datetime_utc.isoformat()
                if next_event.datetime_utc is not None
                else None
            ),
        }

    payload: dict[str, Any] = {
        "risk_multiplier": multiplier,
        "generated_at": now.isoformat(),
        "reasons": reasons,
        "news_high_impact": news_tripped,
        "drawdown_pct": dd_day_pnl / dd_limit if dd_limit > 0 else 0.0,
        "drawdown_pct_of_limit_used": pct_used,
        "within_drawdown_buffer": dd_tripped,
        "next_event": next_event_info,
        "config": asdict(cfg),
    }
    return payload


def write_risk_state(payload: dict[str, Any], path: str) -> None:
    """Atomically write the risk-state JSON: temp file then os.replace."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def run(cfg: RiskConfig) -> dict[str, Any]:
    """Evaluate the risk conditions and write the risk-state file."""
    payload = evaluate(cfg)
    write_risk_state(payload, cfg.out_path)
    logger.info(
        "Wrote risk_state to %s (risk_multiplier=%s, reasons=%s)",
        cfg.out_path,
        payload["risk_multiplier"],
        payload["reasons"],
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    # Load .env if python-dotenv is available, but don't hard-require it.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Interstellar risk layer")
    parser.add_argument("--fmp-key", default=os.getenv("FMP_API_KEY"))
    parser.add_argument("--max-daily-drawdown", type=float, default=0.0)
    parser.add_argument("--day-pnl", type=float, default=None)
    parser.add_argument("--account-state", default=None)
    parser.add_argument("--news-source", choices=["fmp", "forexfactory"], default="fmp")
    parser.add_argument("--window-minutes", type=int, default=60)
    parser.add_argument("--currencies", nargs="+", default=["USD"])
    parser.add_argument("--out", default="output/risk_state.json")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cfg = RiskConfig(
        fmp_api_key=args.fmp_key,
        news_window_minutes=args.window_minutes,
        currencies=args.currencies,
        max_daily_drawdown=args.max_daily_drawdown,
        out_path=args.out,
        account_state_path=args.account_state,
        news_source=args.news_source,
    )
    # If --day-pnl was supplied, evaluate with it directly then write.
    if args.day_pnl is not None:
        payload = evaluate(cfg, day_pnl=args.day_pnl)
        write_risk_state(payload, cfg.out_path)
        logger.info(
            "Wrote risk_state to %s (risk_multiplier=%s, reasons=%s)",
            cfg.out_path,
            payload["risk_multiplier"],
            payload["reasons"],
        )
    else:
        run(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
