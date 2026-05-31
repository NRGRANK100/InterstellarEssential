"""
Walk-forward analysis.

Optimizing a single window invites overfitting: the search will happily find
parameters that only worked because of that window's noise. Walk-forward
analysis fights this by splitting history into consecutive (in-sample,
out-of-sample) folds:

    |--- IS 1 ---|- OOS 1 -|
                 |--- IS 2 ---|- OOS 2 -|
                              |--- IS 3 ---|- OOS 3 -|

For a given parameter set we score every OOS slice and aggregate. Parameters
only score well if they generalize forward across multiple unseen windows.

The aggregated objective uses the *mean OOS score* penalized by its
dispersion, so consistent-but-modest beats brilliant-but-fragile:

    wf_score = mean(oos_scores) * (1 - cv_penalty * coeff_of_variation)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import run_backtest


@dataclass
class WFConfig:
    n_splits: int = 4          # number of OOS folds
    oos_frac: float = 0.25     # each OOS window = this fraction of its fold
    cv_penalty: float = 0.5    # how hard to punish inconsistent OOS scores
    cost_bps: float = 1.0


def _fold_bounds(n: int, cfg: WFConfig):
    """Yield (is_slice, oos_slice) index ranges with an expanding IS window."""
    fold = n // (cfg.n_splits + 1)
    if fold < 10:
        # not enough data to split meaningfully -> single in/out split
        cut = int(n * (1 - cfg.oos_frac))
        yield slice(0, cut), slice(cut, n)
        return
    for k in range(1, cfg.n_splits + 1):
        is_end = fold * k
        oos_end = min(fold * (k + 1), n)
        if oos_end <= is_end:
            break
        yield slice(0, is_end), slice(is_end, oos_end)


def walk_forward_score(
    df: pd.DataFrame,
    signal_fn,
    params: dict,
    cfg: WFConfig | None = None,
) -> float:
    """
    Score a parameter set across out-of-sample folds.

    `signal_fn` is a strategy from strategies.REGISTRY; `params` are the
    concrete values to test. Returns a single scalar for the optimizer to
    maximize. Returns 0.0 if the params are degenerate.
    """
    cfg = cfg or WFConfig()
    n = len(df)
    oos_scores: list[float] = []

    for _is, oos in _fold_bounds(n, cfg):
        oos_df = df.iloc[oos]
        if len(oos_df) < 5:
            continue
        try:
            sig = signal_fn(oos_df, **params)
        except Exception:
            return 0.0
        res = run_backtest(oos_df, sig, cost_bps=cfg.cost_bps)
        oos_scores.append(res.score)

    if not oos_scores:
        return 0.0

    arr = np.asarray(oos_scores, dtype=float)
    mean = arr.mean()
    if mean <= 0:
        return float(mean)  # already bad; don't bother with the penalty

    cv = arr.std() / mean if mean else 0.0
    return float(mean * max(0.0, 1.0 - cfg.cv_penalty * cv))
