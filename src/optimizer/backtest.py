"""
Vectorized backtester and performance metrics.

Design goals:
  * No Python-level loop over bars — everything is numpy/pandas, so a single
    backtest over ~60 days of 5-minute bars costs well under a millisecond.
    That is what makes a 500k-combination search tractable.
  * No look-ahead: the target position from a strategy is shifted one bar
    forward (you can only act on the *next* bar after a signal forms).
  * Costs are modeled per position change (commission + slippage in bps of
    notional) so the optimizer can't win by overtrading on frictionless data.

The headline objective is:

    score = profit_factor * (1 - max_drawdown)

…exactly as specified for the Sunday Optimizer. `score` is what Optuna
maximizes.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    score: float
    profit_factor: float
    max_drawdown: float       # as a positive fraction, e.g. 0.18 == 18%
    total_return: float
    win_rate: float
    num_trades: int
    sharpe: float

    def as_dict(self) -> dict:
        return asdict(self)


def _max_drawdown(equity: np.ndarray) -> float:
    """Peak-to-trough drawdown of an equity curve, as a positive fraction."""
    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / running_max
    return float(-drawdowns.min()) if drawdowns.size else 0.0


def run_backtest(
    df: pd.DataFrame,
    target_position: pd.Series,
    *,
    cost_bps: float = 1.0,        # round-trip-ish friction per unit turnover, in bps
    starting_equity: float = 1.0,
    periods_per_year: int = 252 * 78,  # 5-min bars in a US equity session ≈ 78/day
) -> BacktestResult:
    """
    Turn a target-position series into a scored result.

    `target_position` holds the desired exposure in {-1, 0, +1} per bar.
    We shift it forward one bar, apply it to bar-to-bar close returns, and
    subtract transaction costs whenever the position changes.
    """
    close = df["close"].to_numpy(dtype=float)
    pos = target_position.reindex(df.index).fillna(0.0).to_numpy(dtype=float)

    # act on the NEXT bar -> shift exposure forward by one
    held = np.empty_like(pos)
    held[0] = 0.0
    held[1:] = pos[:-1]

    bar_ret = np.zeros_like(close)
    bar_ret[1:] = close[1:] / close[:-1] - 1.0

    gross = held * bar_ret

    # turnover = |change in position| each bar; cost charged proportionally
    turnover = np.abs(np.diff(held, prepend=0.0))
    cost = turnover * (cost_bps / 1e4)
    net = gross - cost

    equity = starting_equity * np.cumprod(1.0 + net)

    # ── metrics ────────────────────────────────────────────────────────
    gains = net[net > 0].sum()
    losses = -net[net < 0].sum()
    if losses <= 0:
        # no losing bars: avoid div-by-zero, reward but keep finite
        profit_factor = float(gains / 1e-9) if gains > 0 else 0.0
    else:
        profit_factor = float(gains / losses)

    max_dd = _max_drawdown(equity)
    total_return = float(equity[-1] / starting_equity - 1.0)

    # trade-level stats: a "trade" = a span of constant nonzero exposure
    num_trades = int((turnover > 0).sum())
    win_bars = int((net > 0).sum())
    active_bars = int((net != 0).sum())
    win_rate = float(win_bars / active_bars) if active_bars else 0.0

    std = net.std()
    sharpe = float(net.mean() / std * np.sqrt(periods_per_year)) if std > 0 else 0.0

    # primary objective
    score = profit_factor * (1.0 - max_dd)
    # guard rails: a strategy that never trades shouldn't look attractive
    if num_trades < 2 or not np.isfinite(score):
        score = 0.0

    return BacktestResult(
        score=float(score),
        profit_factor=profit_factor,
        max_drawdown=max_dd,
        total_return=total_return,
        win_rate=win_rate,
        num_trades=num_trades,
        sharpe=sharpe,
    )
