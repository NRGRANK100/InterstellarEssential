"""
Module 5 — Robinhood broker connector.

This package replaces the NinjaTrader execution edge with a live Python path
into Robinhood (equities), while reusing the rest of the pipeline unchanged:

    Optimizer  -> output/active_params.json   (champion strategy + params)
    Risk       -> output/risk_state.json       (risk_multiplier)
                         │
                         ▼
    broker/  RobinhoodClient  +  LiveTrader
                         │
                         ▼
    Robinhood account  (orders)  ->  output/executions.csv  (for the audit)

The `LiveTrader` evaluates the optimizer's own strategy functions on live bars
(so backtest and live logic are identical), sizes orders as
`base_quantity * risk_multiplier`, and records fills for the monitoring audit.
"""

from __future__ import annotations

from .client import BrokerError, RobinhoodClient
from .risk_state import read_risk_multiplier
from .trader import LiveTrader, TraderConfig

__all__ = [
    "RobinhoodClient",
    "BrokerError",
    "LiveTrader",
    "TraderConfig",
    "read_risk_multiplier",
]
