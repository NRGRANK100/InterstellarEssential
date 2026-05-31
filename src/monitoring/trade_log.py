"""
Trade log — trade & execution data model and loaders for Module 4.

Spec mapping
------------
Supports the monitoring reports ("daily trades, PnL, and win rate") and the
execution audit by providing a normalised :class:`Trade` model plus tolerant
loaders for NinjaTrader-style broker executions (CSV) and backtest trades
(JSON).  Pure helpers (e.g. :func:`daily_stats`) are deterministic and unit
testable without any I/O.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Union


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Trade:
    """A single trade (entry, and optionally exit).

    ``side`` is "long" or "short".  ``pnl`` may be supplied directly or
    computed from entry/exit prices via :meth:`computed_pnl`.
    """

    timestamp: datetime
    symbol: str
    side: str  # "long" | "short"
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None

    def computed_pnl(self) -> Optional[float]:
        """Return ``pnl`` if set, else compute it from entry/exit when known."""
        if self.pnl is not None:
            return self.pnl
        if self.exit_price is None:
            return None
        direction = 1.0 if self.side.lower() == "long" else -1.0
        return direction * (self.exit_price - self.entry_price) * self.quantity

    def realized_pnl(self) -> float:
        """Like :meth:`computed_pnl` but returns 0.0 when PnL is unknown."""
        val = self.computed_pnl()
        return float(val) if val is not None else 0.0


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
def _parse_timestamp(value: Union[str, datetime, None]) -> datetime:
    """Parse a timestamp from common NinjaTrader / ISO formats."""
    if isinstance(value, datetime):
        return value
    if value is None or str(value).strip() == "":
        return datetime.min
    text = str(value).strip()
    # Try ISO first.
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.min


def _side_from_action(action: str) -> str:
    """Map a NinjaTrader Action ('Buy'/'Sell'/'SellShort') to long/short."""
    a = (action or "").strip().lower()
    if a in ("sell", "sellshort", "sell short", "short"):
        return "short"
    return "long"


def _first_key(row: Dict[str, str], *names: str) -> Optional[str]:
    """Return the value for the first matching key (case-insensitive)."""
    lower = {k.lower().strip(): v for k, v in row.items() if k is not None}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def _to_float(value: Optional[str], default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def load_executions_csv(path: str) -> List[Trade]:
    """Load actual broker executions from a NinjaTrader-style CSV.

    Tolerant of common column names: Time/Timestamp/Date, Instrument/Symbol,
    Action/Side, Quantity/Qty, Price/Fill Price, and optional PnL/Profit.
    """
    trades: List[Trade] = []
    with open(path, "r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ts = _parse_timestamp(_first_key(row, "Time", "Timestamp", "Date", "Date/Time"))
            symbol = _first_key(row, "Instrument", "Symbol", "Market") or ""
            action = _first_key(row, "Action", "Side", "Direction") or "Buy"
            side = _side_from_action(action)
            qty = _to_float(_first_key(row, "Quantity", "Qty", "Size"), 0.0)
            price = _to_float(_first_key(row, "Price", "Fill Price", "FillPrice", "AvgPrice"), 0.0)
            exit_raw = _first_key(row, "Exit Price", "ExitPrice")
            exit_price = _to_float(exit_raw) if exit_raw not in (None, "") else None
            pnl_raw = _first_key(row, "PnL", "Profit", "Realized PnL", "RealizedPnL")
            pnl = _to_float(pnl_raw) if pnl_raw not in (None, "") else None
            trades.append(
                Trade(
                    timestamp=ts,
                    symbol=symbol.strip(),
                    side=side,
                    quantity=qty,
                    entry_price=price,
                    exit_price=exit_price,
                    pnl=pnl,
                )
            )
    return trades


def load_trades_json(path: str) -> List[Trade]:
    """Load trades from a JSON file (list of objects or {"trades": [...]})."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("trades", [])
    trades: List[Trade] = []
    for obj in data:
        trades.append(
            Trade(
                timestamp=_parse_timestamp(obj.get("timestamp")),
                symbol=str(obj.get("symbol", "")),
                side=str(obj.get("side", "long")).lower(),
                quantity=float(obj.get("quantity", 0.0)),
                entry_price=float(obj.get("entry_price", 0.0)),
                exit_price=(None if obj.get("exit_price") is None else float(obj["exit_price"])),
                pnl=(None if obj.get("pnl") is None else float(obj["pnl"])),
            )
        )
    return trades


# --------------------------------------------------------------------------- #
# Pure statistics
# --------------------------------------------------------------------------- #
def daily_stats(trades: Sequence[Trade], day: Optional[date] = None) -> Dict[str, float]:
    """Compute daily summary statistics over ``trades``.

    If ``day`` is given, only trades on that date are considered; otherwise all
    supplied trades are used.  Returns counts, gross PnL, win rate and extremes.
    """
    if day is not None:
        selected = [t for t in trades if t.timestamp.date() == day]
    else:
        selected = list(trades)

    pnls = [t.realized_pnl() for t in selected]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    num = len(selected)
    gross = sum(pnls)
    decided = wins + losses

    return {
        "num_trades": num,
        "gross_pnl": gross,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / decided) if decided else 0.0,
        "largest_win": max(pnls) if pnls else 0.0,
        "largest_loss": min(pnls) if pnls else 0.0,
        "avg_pnl": (gross / num) if num else 0.0,
    }
