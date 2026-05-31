"""
Smoke + correctness tests for the Sunday Optimizer (Module 1).

These run entirely on synthetic data — no network, no yfinance — so they're
safe in CI and on the web sandbox.

Run:  python -m pytest tests/ -q     (or just `python tests/test_optimizer.py`)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.optimizer import strategies as strat_mod          # noqa: E402
from src.optimizer.backtest import run_backtest             # noqa: E402
from src.optimizer.walk_forward import WFConfig, walk_forward_score  # noqa: E402
from src.optimizer.sunday_optimizer import _optimize_one    # noqa: E402


def make_synthetic(n: int = 3000, seed: int = 7) -> pd.DataFrame:
    """A trending-with-noise random walk so strategies have something to find."""
    rng = np.random.default_rng(seed)
    drift = np.linspace(0, 0.4, n)
    noise = rng.normal(0, 0.004, n).cumsum()
    close = 100 * np.exp(drift + noise)
    idx = pd.date_range("2026-01-01", periods=n, freq="5min", name="datetime")
    high = close * (1 + rng.uniform(0, 0.002, n))
    low = close * (1 - rng.uniform(0, 0.002, n))
    open_ = np.r_[close[0], close[:-1]]
    vol = rng.integers(1000, 5000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def test_all_strategies_emit_valid_signals():
    df = make_synthetic()
    for name, strat in strat_mod.REGISTRY.items():
        # use the low end of each range as a concrete param set
        params = {}
        for pname, spec in strat.space.items():
            params[pname] = spec[1] if spec[0] != "cat" else spec[1][0]
        sig = strat.fn(df, **params)
        assert len(sig) == len(df), f"{name}: wrong length"
        assert set(np.unique(sig.dropna())).issubset({-1.0, 0.0, 1.0}), \
            f"{name}: signals not in {{-1,0,1}}"


def test_registry_has_ten_strategies():
    assert len(strat_mod.REGISTRY) == 10, strat_mod.list_strategies()


def test_backtest_metrics_are_sane():
    df = make_synthetic()
    sig = strat_mod.REGISTRY["ema_crossover"].fn(df, fast=10, slow=50)
    res = run_backtest(df, sig)
    assert 0.0 <= res.max_drawdown <= 1.0
    assert res.profit_factor >= 0.0
    assert res.num_trades >= 0
    assert np.isfinite(res.score)
    # score == profit_factor * (1 - max_dd) per the spec
    assert abs(res.score - res.profit_factor * (1 - res.max_drawdown)) < 1e-9 \
        or res.score == 0.0


def test_no_lookahead_flat_signal_is_flat():
    df = make_synthetic()
    flat = pd.Series(0.0, index=df.index)
    res = run_backtest(df, flat)
    assert res.total_return == 0.0
    assert res.num_trades == 0
    assert res.score == 0.0


def test_walk_forward_returns_scalar():
    df = make_synthetic()
    score = walk_forward_score(
        df, strat_mod.REGISTRY["sma_crossover"].fn,
        {"fast": 10, "slow": 50}, WFConfig(n_splits=3),
    )
    assert isinstance(score, float) and np.isfinite(score)


def test_optimize_one_small_budget():
    """End-to-end worker path with a tiny trial budget."""
    df = make_synthetic()
    wf_kwargs = dict(n_splits=3, oos_frac=0.25, cv_penalty=0.5, cost_bps=1.0)
    out = _optimize_one(("rsi_reversion", df, 15, wf_kwargs, 42))
    assert out["strategy"] == "rsi_reversion"
    assert set(out["params"]) == set(strat_mod.REGISTRY["rsi_reversion"].space)
    assert np.isfinite(out["wf_score"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")
