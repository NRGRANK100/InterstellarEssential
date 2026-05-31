"""Module 4 — the Monitoring System package.

Exposes the notifier abstraction, trade/execution model & loaders, report
builders, and the execution audit.
"""
from .audit import audit_executions, audit_report
from .notifier import (
    ConsoleNotifier,
    DiscordNotifier,
    Notifier,
    TelegramNotifier,
    make_notifier,
)
from .reports import daily_report, strategy_of_the_week
from .trade_log import (
    Trade,
    daily_stats,
    load_executions_csv,
    load_trades_json,
)

__all__ = [
    "Notifier",
    "ConsoleNotifier",
    "DiscordNotifier",
    "TelegramNotifier",
    "make_notifier",
    "Trade",
    "daily_stats",
    "load_executions_csv",
    "load_trades_json",
    "daily_report",
    "strategy_of_the_week",
    "audit_executions",
    "audit_report",
]
