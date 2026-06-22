"""
Sunday Optimizer — the weekly self-optimization pass.

What it does, end to end:
  1. Load market data (yfinance or NinjaTrader CSV).
  2. Trim to the evaluation window (default: last 30 days).
  3. For each of the 10 strategies, run an Optuna study whose objective is a
     walk-forward score (profit_factor * (1 - max_drawdown), aggregated OOS).
  4. Run the 10 studies IN PARALLEL across CPU cores via a process pool, so
     the full ~500k-combination budget finishes in minutes, not hours.
  5. Re-score each winner on the held-out final window, rank by the headline
     objective, and write the champion's parameters to a JSON file that the
     NinjaScript strategy reads at session start.

Run it:

    python -m src.optimizer.sunday_optimizer \
        --source yfinance --symbol SPY --interval 5m --period 60d \
        --total-trials 500000 --out output/active_params.json

The ~500k budget is divided evenly across the 10 strategies (≈50k trials
each). Optuna's TPE sampler + median pruner means we explore the space far
more efficiently than a blind 500k-point grid would.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from . import strategies as strat_mod
from .backtest import run_backtest
from .data import load_data
from .walk_forward import WFConfig, walk_forward_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(processName)-14s %(levelname)-7s %(message)s",
)
log = logging.getLogger("sunday_optimizer")

DEFAULT_TOTAL_TRIALS = 500_000
EVAL_DAYS = 30


# ── Optuna objective ────────────────────────────────────────────────────


def _suggest(trial, space: dict) -> dict:
    """Translate a strategy's `space` dict into concrete Optuna suggestions."""
    params: dict = {}
    for name, spec in space.items():
        kind = spec[0]
        if kind == "int":
            _, lo, hi = spec[:3]
            step = spec[3] if len(spec) > 3 else 1
            params[name] = trial.suggest_int(name, lo, hi, step=step)
        elif kind == "float":
            _, lo, hi = spec[:3]
            params[name] = trial.suggest_float(name, lo, hi)
        elif kind == "cat":
            params[name] = trial.suggest_categorical(name, spec[1])
        else:
            raise ValueError(f"Unknown param kind {kind!r} for {name!r}")
    return params


def _optimize_one(args) -> dict:
    """
    Worker entry point: optimize a single strategy. Runs in its own process.

    Receives a picklable bundle (DataFrames pickle fine) and returns the best
    params + their walk-forward score. Kept module-level so ProcessPoolExecutor
    can pickle it.
    """
    strat_name, df_pickle, n_trials, wf_kwargs, seed = args

    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    df: pd.DataFrame = pd.read_pickle(df_pickle) if isinstance(df_pickle, str) else df_pickle
    strategy = strat_mod.REGISTRY[strat_name]
    wf_cfg = WFConfig(**wf_kwargs)

    def objective(trial):
        params = _suggest(trial, strategy.space)
        return walk_forward_score(df, strategy.fn, params, wf_cfg)

    sampler = optuna.samplers.TPESampler(seed=seed, multivariate=True)
    pruner = optuna.pruners.MedianPruner(n_warmup_steps=0)
    study = optuna.create_study(
        direction="maximize", sampler=sampler, pruner=pruner
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    return {
        "strategy": strat_name,
        "wf_score": float(study.best_value),
        "params": dict(study.best_params),
        "n_trials": n_trials,
    }


# ── orchestration ───────────────────────────────────────────────────────


@dataclass
class OptimizerConfig:
    source: str = "yfinance"
    symbol: str = "SPY"
    interval: str = "5m"
    period: str = "60d"
    csv_path: str | None = None
    total_trials: int = DEFAULT_TOTAL_TRIALS
    eval_days: int = EVAL_DAYS
    max_workers: int | None = None
    out_path: str = "output/active_params.json"


def _trim_to_window(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if df.empty:
        return df
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df.loc[df.index >= cutoff]


def run(cfg: OptimizerConfig) -> dict:
    # 1. load + window the data
    if cfg.source == "yfinance":
        df = load_data("yfinance", symbol=cfg.symbol, interval=cfg.interval, period=cfg.period)
    elif cfg.source == "robinhood":
        # same feed the Robinhood connector trades on, so live ≈ backtest
        df = load_data("robinhood", symbol=cfg.symbol, interval=cfg.interval)
    else:
        df = load_data("ninjatrader", path=cfg.csv_path)

    eval_df = _trim_to_window(df, cfg.eval_days)
    log.info(
        "Loaded %d bars for %s; evaluating last %d days (%d bars)",
        len(df), cfg.symbol, cfg.eval_days, len(eval_df),
    )
    if len(eval_df) < 50:
        raise RuntimeError("Not enough bars in evaluation window to optimize.")

    # 2. divide the trial budget across strategies
    names = strat_mod.list_strategies()
    per_strategy = max(1, cfg.total_trials // len(names))
    log.info("Budget: %d trials total -> %d per strategy across %d strategies",
             cfg.total_trials, per_strategy, len(names))

    # ship the DataFrame to workers via a temp pickle (cheaper than re-pickling
    # per task, and avoids re-downloading data in each process)
    os.makedirs("output", exist_ok=True)
    df_pickle = os.path.abspath("output/_eval_window.pkl")
    eval_df.to_pickle(df_pickle)

    wf_kwargs = dict(n_splits=4, oos_frac=0.25, cv_penalty=0.5, cost_bps=1.0)
    tasks = [
        (name, df_pickle, per_strategy, wf_kwargs, 1000 + i)
        for i, name in enumerate(names)
    ]

    # 3. optimize all strategies in parallel
    workers = cfg.max_workers or min(len(names), os.cpu_count() or 1)
    log.info("Launching %d worker processes…", workers)
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_optimize_one, t): t[0] for t in tasks}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                res = fut.result()
                results.append(res)
                log.info("  %-20s wf_score=%.4f params=%s",
                         res["strategy"], res["wf_score"], res["params"])
            except Exception as exc:  # one bad strategy shouldn't sink the run
                log.exception("Strategy %s failed: %s", name, exc)

    if not results:
        raise RuntimeError("All strategy optimizations failed.")

    # 4. final scoring on the full evaluation window + pick the champion
    ranked = []
    for res in results:
        strategy = strat_mod.REGISTRY[res["strategy"]]
        sig = strategy.fn(eval_df, **res["params"])
        final = run_backtest(eval_df, sig, cost_bps=wf_kwargs["cost_bps"])
        ranked.append({**res, "final": final.as_dict()})

    # rank by the headline objective on the eval window, tie-break on WF score
    ranked.sort(key=lambda r: (r["final"]["score"], r["wf_score"]), reverse=True)
    champion = ranked[0]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": cfg.symbol,
        "interval": cfg.interval,
        "eval_days": cfg.eval_days,
        "objective": "profit_factor * (1 - max_drawdown)",
        "champion": {
            "strategy": champion["strategy"],
            "params": champion["params"],
            "score": champion["final"]["score"],
            "metrics": champion["final"],
            "wf_score": champion["wf_score"],
        },
        "leaderboard": [
            {
                "strategy": r["strategy"],
                "score": r["final"]["score"],
                "profit_factor": r["final"]["profit_factor"],
                "max_drawdown": r["final"]["max_drawdown"],
                "wf_score": r["wf_score"],
            }
            for r in ranked
        ],
    }

    os.makedirs(os.path.dirname(os.path.abspath(cfg.out_path)), exist_ok=True)
    with open(cfg.out_path, "w") as fh:
        json.dump(payload, fh, indent=2)
    log.info("Champion: %s  score=%.4f  ->  wrote %s",
             champion["strategy"], champion["final"]["score"], cfg.out_path)

    return payload


# ── CLI ─────────────────────────────────────────────────────────────────


def _parse_args(argv=None) -> OptimizerConfig:
    p = argparse.ArgumentParser(description="Sunday Optimizer for NinjaTrader 8 pipeline")
    p.add_argument("--source", choices=["yfinance", "ninjatrader", "robinhood"],
                   default="yfinance")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--interval", default="5m")
    p.add_argument("--period", default="60d")
    p.add_argument("--csv-path", default=None, help="NinjaTrader CSV (when --source ninjatrader)")
    p.add_argument("--total-trials", type=int, default=DEFAULT_TOTAL_TRIALS)
    p.add_argument("--eval-days", type=int, default=EVAL_DAYS)
    p.add_argument("--max-workers", type=int, default=None)
    p.add_argument("--out", dest="out_path", default="output/active_params.json")
    a = p.parse_args(argv)
    return OptimizerConfig(
        source=a.source, symbol=a.symbol, interval=a.interval, period=a.period,
        csv_path=a.csv_path, total_trials=a.total_trials, eval_days=a.eval_days,
        max_workers=a.max_workers, out_path=a.out_path,
    )


if __name__ == "__main__":
    run(_parse_args())
