"""Module 3: Risk Layer (news + drawdown -> risk_multiplier)."""
from __future__ import annotations

from src.risk.drawdown import read_account_state, within_drawdown_buffer
from src.risk.engine import RiskConfig, evaluate, run, write_risk_state
from src.risk.news import (
    NewsEvent,
    fetch_fmp_economic_calendar,
    fetch_forexfactory_calendar,
    has_high_impact_news,
)

__all__ = [
    "NewsEvent",
    "fetch_fmp_economic_calendar",
    "fetch_forexfactory_calendar",
    "has_high_impact_news",
    "within_drawdown_buffer",
    "read_account_state",
    "RiskConfig",
    "evaluate",
    "run",
    "write_risk_state",
]
