"""
Ten vectorized trading strategies.

Each strategy is a pure function:

    signal(df: DataFrame, **params) -> pd.Series   # target position in {-1, 0, +1}

The returned series is the *desired* position for each bar. The backtester
shifts it by one bar (trade on next open) to avoid look-ahead bias, so the
signal functions here are free to use the current bar's close.

Every strategy also publishes a `space` dict describing its parameter search
ranges. The optimizer turns these into Optuna suggestions. Keeping the search
space next to the logic means adding a strategy is a single self-contained
edit.

The total search budget (~500k combinations) is split across these 10
strategies by the Sunday Optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

# ── small vectorized indicator helpers ──────────────────────────────────


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _stoch_k(df: pd.DataFrame, n: int) -> pd.Series:
    low_n = df["low"].rolling(n).min()
    high_n = df["high"].rolling(n).max()
    return 100.0 * (df["close"] - low_n) / (high_n - low_n).replace(0.0, np.nan)


# ── strategy registry plumbing ──────────────────────────────────────────


@dataclass(frozen=True)
class Strategy:
    name: str
    fn: Callable[..., pd.Series]
    space: dict  # param -> ("int"|"float"|"cat", low, high[, step]) or list for cat


REGISTRY: dict[str, Strategy] = {}


def register(name: str, space: dict):
    def deco(fn: Callable[..., pd.Series]) -> Callable[..., pd.Series]:
        REGISTRY[name] = Strategy(name=name, fn=fn, space=space)
        return fn

    return deco


# ── the ten strategies ──────────────────────────────────────────────────


@register("sma_crossover", {
    "fast": ("int", 3, 50),
    "slow": ("int", 20, 200),
})
def sma_crossover(df, fast, slow):
    if fast >= slow:
        return pd.Series(0, index=df.index)
    f, s = _sma(df["close"], fast), _sma(df["close"], slow)
    return np.sign(f - s).fillna(0)


@register("ema_crossover", {
    "fast": ("int", 3, 50),
    "slow": ("int", 20, 200),
})
def ema_crossover(df, fast, slow):
    if fast >= slow:
        return pd.Series(0, index=df.index)
    f, s = _ema(df["close"], fast), _ema(df["close"], slow)
    return np.sign(f - s).fillna(0)


@register("rsi_reversion", {
    "period": ("int", 5, 30),
    "lower": ("int", 15, 40),
    "upper": ("int", 60, 85),
})
def rsi_reversion(df, period, lower, upper):
    rsi = _rsi(df["close"], period)
    pos = pd.Series(np.nan, index=df.index)
    pos[rsi < lower] = 1.0     # oversold -> long
    pos[rsi > upper] = -1.0    # overbought -> short
    return pos.ffill().fillna(0)


@register("bollinger_breakout", {
    "period": ("int", 10, 60),
    "mult": ("float", 1.0, 3.5),
})
def bollinger_breakout(df, period, mult):
    mid = _sma(df["close"], period)
    sd = df["close"].rolling(period).std()
    upper, lower = mid + mult * sd, mid - mult * sd
    pos = pd.Series(np.nan, index=df.index)
    pos[df["close"] > upper] = 1.0
    pos[df["close"] < lower] = -1.0
    return pos.ffill().fillna(0)


@register("macd", {
    "fast": ("int", 5, 30),
    "slow": ("int", 20, 60),
    "signal": ("int", 5, 20),
})
def macd(df, fast, slow, signal):
    if fast >= slow:
        return pd.Series(0, index=df.index)
    macd_line = _ema(df["close"], fast) - _ema(df["close"], slow)
    sig = _ema(macd_line, signal)
    return np.sign(macd_line - sig).fillna(0)


@register("donchian_breakout", {
    "period": ("int", 10, 100),
})
def donchian_breakout(df, period):
    hi = df["high"].rolling(period).max().shift(1)
    lo = df["low"].rolling(period).min().shift(1)
    pos = pd.Series(np.nan, index=df.index)
    pos[df["close"] > hi] = 1.0
    pos[df["close"] < lo] = -1.0
    return pos.ffill().fillna(0)


@register("momentum", {
    "lookback": ("int", 5, 120),
    "threshold": ("float", 0.0, 0.02),
})
def momentum(df, lookback, threshold):
    roc = df["close"].pct_change(lookback)
    pos = pd.Series(0.0, index=df.index)
    pos[roc > threshold] = 1.0
    pos[roc < -threshold] = -1.0
    return pos.fillna(0)


@register("stochastic", {
    "period": ("int", 5, 30),
    "lower": ("int", 10, 35),
    "upper": ("int", 65, 90),
})
def stochastic(df, period, lower, upper):
    k = _stoch_k(df, period)
    pos = pd.Series(np.nan, index=df.index)
    pos[k < lower] = 1.0
    pos[k > upper] = -1.0
    return pos.ffill().fillna(0)


@register("atr_breakout", {
    "period": ("int", 5, 40),
    "mult": ("float", 0.5, 4.0),
})
def atr_breakout(df, period, mult):
    atr = _atr(df, period)
    ref = df["close"].shift(1)
    pos = pd.Series(np.nan, index=df.index)
    pos[df["close"] > ref + mult * atr] = 1.0
    pos[df["close"] < ref - mult * atr] = -1.0
    return pos.ffill().fillna(0)


@register("vwap_reversion", {
    "period": ("int", 10, 120),
    "band": ("float", 0.5, 3.0),
})
def vwap_reversion(df, period, band):
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    rolling_vwap = (
        (tp * df["volume"]).rolling(period).sum()
        / df["volume"].rolling(period).sum().replace(0.0, np.nan)
    )
    dist = (df["close"] - rolling_vwap)
    sd = dist.rolling(period).std()
    pos = pd.Series(np.nan, index=df.index)
    pos[dist > band * sd] = -1.0   # stretched above VWAP -> fade
    pos[dist < -band * sd] = 1.0   # stretched below VWAP -> buy
    return pos.ffill().fillna(0)


def list_strategies() -> list[str]:
    return list(REGISTRY)
