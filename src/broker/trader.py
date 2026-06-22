"""
LiveTrader — evaluate the champion strategy on live bars and trade Robinhood.

One evaluation cycle (`step`):
  1. Read the champion strategy + params from active_params.json.
  2. Pull live bars from the broker and compute the *same* signal function the
     optimizer/backtester used -> desired position in {-1, 0, +1}.
  3. Read the risk multiplier from risk_state.json and size the order as
     `base_quantity * risk_multiplier` (rounded down, never upsized).
  4. Reconcile against the current broker position and place the delta as a
     market order. Robinhood equities are long-only, so a short signal (-1) is
     treated as flat (exit) unless `allow_short` maps it elsewhere.
  5. Append any fill to executions.csv so the monitoring audit can compare it
     against expected backtest trades.

Designed to be driven on a schedule (cron / a loop) — `step()` is a single
idempotent pass so a crash between cycles never double-trades beyond one delta.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.optimizer.strategies import REGISTRY
from .client import RobinhoodClient
from .risk_state import read_risk_multiplier

log = logging.getLogger("broker.trader")


@dataclass
class TraderConfig:
    symbol: str = "SPY"
    interval: str = "5minute"
    base_quantity: int = 1
    params_path: str = "output/active_params.json"
    risk_path: str = "output/risk_state.json"
    executions_path: str = "output/executions.csv"
    allow_short: bool = False           # Robinhood cash/most accounts: long-only


@dataclass
class LiveTrader:
    client: RobinhoodClient
    cfg: TraderConfig = field(default_factory=TraderConfig)

    # ── champion loading ────────────────────────────────────────────────
    def _load_champion(self) -> tuple[str, dict]:
        payload = json.loads(Path(self.cfg.params_path).read_text())
        champ = payload["champion"]
        name = champ["strategy"]
        if name not in REGISTRY:
            raise KeyError(f"Unknown champion strategy '{name}'. Known: {sorted(REGISTRY)}")
        return name, dict(champ["params"])

    # ── signal ──────────────────────────────────────────────────────────
    def desired_position(self) -> int:
        """Latest target position in {-1,0,1} from the champion strategy."""
        name, params = self._load_champion()
        df = self.client.get_history(self.cfg.symbol, self.cfg.interval)
        sig = REGISTRY[name].fn(df, **params)
        # last non-NaN signal; default flat
        sig = sig.reindex(df.index).fillna(0.0)
        last = int(sig.iloc[-1]) if len(sig) else 0
        if last < 0 and not self.cfg.allow_short:
            return 0  # long-only account: a short signal means "be flat"
        return last

    # ── sizing ──────────────────────────────────────────────────────────
    def target_shares(self, desired: int) -> int:
        """Signed target share count after applying the risk multiplier."""
        mult = read_risk_multiplier(self.cfg.risk_path)
        qty = math.floor(self.cfg.base_quantity * mult)
        return desired * max(0, qty)

    # ── one cycle ───────────────────────────────────────────────────────
    def step(self) -> dict:
        """Run one evaluate->reconcile->order cycle. Returns a summary dict."""
        desired = self.desired_position()
        target = self.target_shares(desired)
        current = int(round(self.client.get_position_qty(self.cfg.symbol)))
        delta = target - current

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": self.cfg.symbol,
            "desired_position": desired,
            "target_shares": target,
            "current_shares": current,
            "delta": delta,
            "order": None,
        }

        if delta == 0:
            log.info("%s: already at target (%d shares); no order.", self.cfg.symbol, target)
            return summary

        side = "buy" if delta > 0 else "sell"
        qty = abs(delta)
        order = (self.client.market_buy(self.cfg.symbol, qty) if side == "buy"
                 else self.client.market_sell(self.cfg.symbol, qty))
        summary["order"] = order

        # record the fill for the audit (best-effort price)
        price = order.get("price") or order.get("average_price")
        if price is None:
            try:
                price = self.client.get_price(self.cfg.symbol)
            except Exception:  # pragma: no cover - network
                price = ""
        self._record_execution(summary["timestamp"], side, qty, price)
        log.info("%s: %s %d shares (target=%d, was=%d)",
                 self.cfg.symbol, side.upper(), qty, target, current)
        return summary

    # ── audit trail ─────────────────────────────────────────────────────
    def _record_execution(self, ts: str, side: str, qty: int, price) -> None:
        path = self.cfg.executions_path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        new_file = not os.path.exists(path)
        try:
            with open(path, "a", newline="") as fh:
                w = csv.writer(fh)
                if new_file:
                    w.writerow(["Time", "Symbol", "Action", "Quantity", "Price"])
                w.writerow([ts, self.cfg.symbol, side.upper(), qty, price])
        except Exception as exc:  # pragma: no cover
            log.warning("could not record execution: %s", exc)
