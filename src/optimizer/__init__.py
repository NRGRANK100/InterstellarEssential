"""Sunday Optimizer package — Module 1 of the Interstellar Essential pipeline."""

from .backtest import BacktestResult, run_backtest
from .sunday_optimizer import OptimizerConfig, run
from .walk_forward import WFConfig, walk_forward_score

__all__ = [
    "BacktestResult",
    "run_backtest",
    "OptimizerConfig",
    "run",
    "WFConfig",
    "walk_forward_score",
]
