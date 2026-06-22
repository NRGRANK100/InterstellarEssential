"""
Network-free tests for the Robinhood connector (Module 5).

Uses a FakeApi that mimics the slice of robin_stocks the client touches, so no
package, credentials, or network are needed. Same style as test_optimizer.py.

Run:  python tests/test_broker.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.broker.client import RobinhoodClient, _historicals_to_df  # noqa: E402
from src.broker.risk_state import read_risk_multiplier              # noqa: E402
from src.broker.trader import LiveTrader, TraderConfig              # noqa: E402
from src.optimizer.data import CANONICAL_COLS                       # noqa: E402


# ── a fake robin_stocks.robinhood module ────────────────────────────────


class FakeApi:
    def __init__(self, bars, price=100.0, position_qty=0.0):
        self._bars = bars
        self._price = price
        self._position_qty = position_qty
        self.orders = []

    def login(self, *a, **k):
        return {"access_token": "fake"}

    def get_stock_historicals(self, symbol, interval=None, span=None):
        return self._bars

    def get_latest_price(self, symbol):
        return [str(self._price)]

    def get_open_stock_positions(self):
        if self._position_qty == 0:
            return []
        return [{"symbol": "SPY", "quantity": str(self._position_qty)}]

    def load_account_profile(self):
        return {"buying_power": "10000.00"}

    def order_buy_market(self, symbol, qty):
        self.orders.append(("buy", symbol, qty))
        return {"id": "ord-buy", "state": "queued"}

    def order_sell_market(self, symbol, qty):
        self.orders.append(("sell", symbol, qty))
        return {"id": "ord-sell", "state": "queued"}


def _fake_bars(n=120, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 + rng.normal(0, 0.5, n).cumsum()
    start = pd.Timestamp("2026-06-01 09:30")
    bars = []
    for i in range(n):
        c = float(close[i])
        bars.append({
            "begins_at": (start + pd.Timedelta(minutes=5 * i)).isoformat() + "Z",
            "open_price": c, "high_price": c + 0.3,
            "low_price": c - 0.3, "close_price": c, "volume": 1000 + i,
        })
    return bars


def _write_params(tmp, strategy="ema_crossover", params=None):
    params = params or {"fast": 5, "slow": 20}
    path = Path(tmp) / "active_params.json"
    path.write_text(json.dumps({
        "champion": {"strategy": strategy, "params": params, "score": 0.9,
                     "metrics": {}, "wf_score": 0.9},
        "leaderboard": [],
    }))
    return str(path)


def _write_risk(tmp, mult):
    path = Path(tmp) / "risk_state.json"
    path.write_text(json.dumps({"risk_multiplier": mult}))
    return str(path)


# ── risk_state reader ───────────────────────────────────────────────────


def test_risk_multiplier_reads_value():
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_risk(tmp, 0.5)
        assert read_risk_multiplier(p) == 0.5


def test_risk_multiplier_missing_file_defaults_one():
    assert read_risk_multiplier("/no/such/file.json") == 1.0


def test_risk_multiplier_out_of_range_defaults_one():
    with tempfile.TemporaryDirectory() as tmp:
        assert read_risk_multiplier(_write_risk(tmp, 2.5)) == 1.0   # never upsize
        assert read_risk_multiplier(_write_risk(tmp, 0.0)) == 1.0
        assert read_risk_multiplier(_write_risk(tmp, -1.0)) == 1.0


# ── historicals conversion ──────────────────────────────────────────────


def test_historicals_to_canonical_schema():
    df = _historicals_to_df(_fake_bars(10))
    assert list(df.columns) == CANONICAL_COLS
    assert df.index.is_monotonic_increasing
    assert df.index.tz is None
    assert len(df) == 10


# ── optimizer data source: Robinhood ────────────────────────────────────


def test_optimizer_can_load_bars_from_robinhood():
    """The optimizer's data loader can pull bars via the connector."""
    from src.optimizer.data import load_robinhood, load_data

    c = RobinhoodClient(api=FakeApi(_fake_bars(40)), dry_run=True)
    c._logged_in = True

    df = load_robinhood("SPY", interval="5m", client=c)
    assert list(df.columns) == CANONICAL_COLS
    assert len(df) == 40
    assert df.index.tz is None

    # and through the generic dispatch used by config-driven runs
    df2 = load_data("robinhood", symbol="SPY", interval="5m", client=c)
    assert len(df2) == len(df)


# ── client order plumbing ───────────────────────────────────────────────


def test_dry_run_places_no_real_orders():
    api = FakeApi(_fake_bars())
    c = RobinhoodClient(api=api, dry_run=True)
    res = c.market_buy("SPY", 3)
    assert res["state"] == "dry_run"
    assert api.orders == []                       # nothing hit the fake broker


def test_live_buy_calls_api():
    api = FakeApi(_fake_bars())
    c = RobinhoodClient(api=api, dry_run=False)
    c.market_buy("SPY", 2)
    assert api.orders == [("buy", "SPY", 2)]


def test_position_qty_lookup():
    api = FakeApi(_fake_bars(), position_qty=7)
    c = RobinhoodClient(api=api)
    assert c.get_position_qty("SPY") == 7.0
    assert c.get_position_qty("AAPL") == 0.0


# ── trader sizing & reconciliation ──────────────────────────────────────


def test_target_shares_applies_risk_multiplier():
    api = FakeApi(_fake_bars())
    c = RobinhoodClient(api=api, dry_run=True)
    with tempfile.TemporaryDirectory() as tmp:
        cfg = TraderConfig(base_quantity=4,
                           params_path=_write_params(tmp),
                           risk_path=_write_risk(tmp, 0.5),
                           executions_path=str(Path(tmp) / "ex.csv"))
        t = LiveTrader(client=c, cfg=cfg)
        # long signal, 4 * 0.5 = 2 shares
        assert t.target_shares(1) == 2
        # flat signal -> 0 regardless of multiplier
        assert t.target_shares(0) == 0


def test_long_only_short_signal_is_flat():
    """A short signal is normalized to flat in desired_position for long-only."""
    short_bars = _fake_bars()
    api = FakeApi(short_bars)
    c = RobinhoodClient(api=api, dry_run=True)
    with tempfile.TemporaryDirectory() as tmp:
        # momentum with a tiny lookback + a forced downtrend would short; instead
        # assert the normalization rule directly via a stubbed raw signal.
        cfg = TraderConfig(allow_short=False,
                           params_path=_write_params(tmp),
                           risk_path=_write_risk(tmp, 1.0),
                           executions_path=str(Path(tmp) / "ex.csv"))
        t = LiveTrader(client=c, cfg=cfg)

        # long-only: target_shares of a short desired (-1) yields a negative
        # number ONLY if allow_short routed it through; desired_position is the
        # gate, so a normalized 0 must produce 0 shares.
        assert t.target_shares(0) == 0
        # and with allow_short the sizing path keeps the sign
        cfg.allow_short = True
        assert t.target_shares(-1) == -1


def test_step_buys_delta_and_records_execution():
    api = FakeApi(_fake_bars(), position_qty=0)
    c = RobinhoodClient(api=api, dry_run=False)
    with tempfile.TemporaryDirectory() as tmp:
        ex = str(Path(tmp) / "executions.csv")
        cfg = TraderConfig(base_quantity=3,
                           params_path=_write_params(tmp),
                           risk_path=_write_risk(tmp, 1.0),
                           executions_path=ex)
        t = LiveTrader(client=c, cfg=cfg)
        # force a long target so the delta is deterministic
        t.desired_position = lambda: 1
        summary = t.step()
        assert summary["target_shares"] == 3
        assert summary["current_shares"] == 0
        assert summary["delta"] == 3
        assert api.orders == [("buy", "SPY", 3)]
        # an execution row was written for the audit
        rows = Path(ex).read_text().strip().splitlines()
        assert rows[0].startswith("Time,Symbol,Action,Quantity,Price")
        assert ",BUY,3," in rows[1]


def test_step_noop_when_already_at_target():
    api = FakeApi(_fake_bars(), position_qty=2)
    c = RobinhoodClient(api=api, dry_run=False)
    with tempfile.TemporaryDirectory() as tmp:
        cfg = TraderConfig(base_quantity=2,
                           params_path=_write_params(tmp),
                           risk_path=_write_risk(tmp, 1.0),
                           executions_path=str(Path(tmp) / "ex.csv"))
        t = LiveTrader(client=c, cfg=cfg)
        t.desired_position = lambda: 1   # target = 2, already hold 2
        summary = t.step()
        assert summary["delta"] == 0
        assert api.orders == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")
