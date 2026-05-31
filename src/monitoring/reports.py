"""
Reports — build human-readable report TEXT for Module 4.

Spec mapping
------------
"...reports daily trades, PnL, and win rate, plus weekly 'Strategy of the Week'
 optimization results."

These functions return formatted strings only; sending is the notifier's job
(separation of concerns keeps them pure & testable).  Formatting is kept
compact so it renders well in both Discord and Telegram.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Optional, Sequence

from .trade_log import Trade, daily_stats


def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def daily_report(
    trades: Sequence[Trade],
    day: Optional[date] = None,
    account_balance: Optional[float] = None,
) -> str:
    """Format the daily trades / PnL / win-rate report."""
    stats = daily_stats(trades, day=day)
    label = day.isoformat() if day else "All sessions"

    lines = [
        "Daily Trading Report",
        f"Date: {label}",
        "-" * 28,
        f"Trades:      {int(stats['num_trades'])}",
        f"Wins/Losses: {int(stats['wins'])}/{int(stats['losses'])}",
        f"Win rate:    {stats['win_rate'] * 100:.1f}%",
        f"Gross PnL:   {_money(stats['gross_pnl'])}",
        f"Avg PnL:     {_money(stats['avg_pnl'])}",
        f"Best trade:  {_money(stats['largest_win'])}",
        f"Worst trade: {_money(stats['largest_loss'])}",
    ]
    if account_balance is not None:
        lines.append(f"Balance:     {_money(account_balance)}")
    return "\n".join(lines)


def strategy_of_the_week(active_params_path: str = "output/active_params.json") -> str:
    """Format the weekly 'Strategy of the Week' from ``active_params.json``."""
    try:
        with open(active_params_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return f"Strategy of the Week unavailable: {active_params_path} not found."
    except json.JSONDecodeError as exc:
        return f"Strategy of the Week unavailable: could not parse params ({exc})."

    champion = data.get("champion", {})
    metrics = champion.get("metrics", {})
    params = champion.get("params", {})

    lines = [
        "Strategy of the Week",
        f"Symbol: {data.get('symbol', '?')} | Interval: {data.get('interval', '?')}"
        f" | Eval days: {data.get('eval_days', '?')}",
        "-" * 28,
        f"Champion:      {champion.get('strategy', '?')}",
        f"Score:         {champion.get('score', metrics.get('score', 0.0)):.3f}",
        f"Profit factor: {metrics.get('profit_factor', 0.0):.2f}",
        f"Max drawdown:  {metrics.get('max_drawdown', 0.0) * 100:.1f}%",
        f"Total return:  {metrics.get('total_return', 0.0) * 100:.1f}%",
        f"Win rate:      {metrics.get('win_rate', 0.0) * 100:.1f}%",
        f"Trades:        {int(metrics.get('num_trades', 0))}",
        f"Sharpe:        {metrics.get('sharpe', 0.0):.2f}",
        f"WF score:      {champion.get('wf_score', 0.0):.3f}",
    ]

    if params:
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        lines.append(f"Params:        {param_str}")

    leaderboard = data.get("leaderboard", [])
    runners = [e for e in leaderboard if e.get("strategy") != champion.get("strategy")]
    if runners:
        lines.append("-" * 28)
        lines.append("Runner-ups:")
        for entry in runners[:3]:
            lines.append(
                f"  {entry.get('strategy', '?')}: "
                f"score {entry.get('score', 0.0):.3f}, "
                f"PF {entry.get('profit_factor', 0.0):.2f}, "
                f"DD {entry.get('max_drawdown', 0.0) * 100:.1f}%"
            )
    return "\n".join(lines)
