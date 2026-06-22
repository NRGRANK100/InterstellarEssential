"""
Data loading for the Sunday Optimizer.

Two sources are supported:
  * yfinance         — free OHLCV, good for research / nightly jobs
  * NinjaTrader CSV  — exported bars from the trading platform itself,
                       which match what the live strategy actually sees.

Everything is normalized to a single canonical schema so the rest of the
pipeline never has to care where the bars came from:

    DataFrame indexed by tz-naive DatetimeIndex, columns:
        ['open', 'high', 'low', 'close', 'volume']
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CANONICAL_COLS = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case columns, coerce schema, sort, drop dupes/NaNs."""
    df = df.rename(columns={c: c.lower() for c in df.columns})
    missing = [c for c in CANONICAL_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Data is missing required columns: {missing}")

    df = df[CANONICAL_COLS].copy()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])

    # tz-naive index keeps comparisons simple across data sources
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df.index.name = "datetime"
    return df


def load_yfinance(
    symbol: str,
    period: str = "60d",
    interval: str = "5m",
) -> pd.DataFrame:
    """
    Pull bars from yfinance.

    Note: intraday intervals (<1d) are limited by Yahoo to ~60 days of
    history, which is fine here — the optimizer evaluates the last 30 days
    and uses the rest for walk-forward in-sample windows.
    """
    import yfinance as yf  # imported lazily so unit tests don't need the dep

    raw = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance returned no data for {symbol!r}")

    # yfinance can return a MultiIndex column frame for single tickers
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    return _normalize(raw)


def load_ninjatrader_csv(path: str | Path) -> pd.DataFrame:
    """
    Load a NinjaTrader-exported CSV.

    NinjaTrader's default historical export is semicolon-delimited with no
    header:  yyyyMMdd HHmmss;open;high;low;close;volume
    We also tolerate a normal comma CSV that already has named columns.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    # Sniff: NinjaTrader native export has no header and uses ';'
    head = path.read_text(errors="ignore").splitlines()[:1]
    is_native = bool(head) and ";" in head[0] and "," not in head[0]

    if is_native:
        df = pd.read_csv(
            path,
            sep=";",
            header=None,
            names=["datetime", "open", "high", "low", "close", "volume"],
        )
        df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d %H%M%S")
        df = df.set_index("datetime")
    else:
        df = pd.read_csv(path)
        # find a datetime-ish column to use as the index
        dt_col = next(
            (c for c in df.columns if c.lower() in ("datetime", "date", "time", "timestamp")),
            df.columns[0],
        )
        df[dt_col] = pd.to_datetime(df[dt_col])
        df = df.set_index(dt_col)

    return _normalize(df)


# map the optimizer's yfinance-style intervals to robin_stocks intervals
_RH_INTERVAL = {
    "5m": "5minute",
    "10m": "10minute",
    "1h": "hour",
    "60m": "hour",
    "1d": "day",
}


def load_robinhood(
    symbol: str,
    interval: str = "5m",
    client: object = None,
) -> pd.DataFrame:
    """
    Pull bars from Robinhood via the Module 5 connector so backtest data
    matches the live execution feed.

    Imported lazily to avoid a circular import (``src.broker`` depends on this
    module). Requires Robinhood credentials in the environment unless a
    pre-built/logged-in ``client`` is injected (handy for tests).
    """
    rh_interval = _RH_INTERVAL.get(interval.lower(), interval)

    if client is None:
        from src.broker.client import RobinhoodClient  # lazy: breaks import cycle

        client = RobinhoodClient()
        client.login()

    # client.get_history already returns the canonical OHLCV schema
    return _normalize(client.get_history(symbol, interval=rh_interval))


def load_data(source: str, **kwargs) -> pd.DataFrame:
    """Dispatch helper used by config-driven runs."""
    source = source.lower()
    if source == "yfinance":
        return load_yfinance(**kwargs)
    if source in ("ninjatrader", "csv", "nt"):
        return load_ninjatrader_csv(**kwargs)
    if source in ("robinhood", "rh"):
        return load_robinhood(**kwargs)
    raise ValueError(f"Unknown data source: {source!r}")
