"""Unit tests for the Monitoring System (Module 4).

Run directly:  ``python tests/test_monitoring.py``
Network-free and deterministic (no Discord/Telegram/HTTP calls).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _trade(ts, side, entry, exit_=None, pnl=None, qty=1.0, symbol="ES"):
    from src.monitoring.trade_log import Trade

    return Trade(
        timestamp=datetime.fromisoformat(ts),
        symbol=symbol,
        side=side,
        quantity=qty,
        entry_price=entry,
        exit_price=exit_,
        pnl=pnl,
    )


def test_daily_stats_and_report():
    from src.monitoring.reports import daily_report
    from src.monitoring.trade_log import daily_stats

    trades = [
        _trade("2026-05-30T10:00:00", "long", 100.0, 110.0),   # +10
        _trade("2026-05-30T11:00:00", "long", 100.0, 95.0),    # -5
        _trade("2026-05-30T12:00:00", "short", 100.0, 90.0),   # +10
    ]
    stats = daily_stats(trades)
    assert stats["num_trades"] == 3, stats
    assert stats["wins"] == 2 and stats["losses"] == 1, stats
    assert abs(stats["gross_pnl"] - 15.0) < 1e-9, stats
    assert abs(stats["win_rate"] - (2 / 3)) < 1e-9, stats
    assert abs(stats["largest_win"] - 10.0) < 1e-9, stats
    assert abs(stats["largest_loss"] - (-5.0)) < 1e-9, stats

    report = daily_report(trades, account_balance=10000.0)
    assert "Daily Trading Report" in report
    assert "66.7%" in report  # win rate
    assert "$15.00" in report
    print("  daily_stats / daily_report OK")


def test_strategy_of_the_week():
    from src.monitoring.reports import strategy_of_the_week

    payload = {
        "generated_at": "2026-05-31T00:00:00+00:00",
        "symbol": "NQ",
        "interval": "5m",
        "eval_days": 30,
        "objective": "profit_factor * (1 - max_drawdown)",
        "champion": {
            "strategy": "ema_cross",
            "params": {"fast": 10, "slow": 30, "stop_atr": 2.0},
            "score": 1.5,
            "metrics": {
                "score": 1.5,
                "profit_factor": 2.0,
                "max_drawdown": 0.25,
                "total_return": 0.5,
                "win_rate": 0.6,
                "num_trades": 42,
                "sharpe": 1.5,
            },
            "wf_score": 1.4,
        },
        "leaderboard": [
            {"strategy": "ema_cross", "score": 1.5, "profit_factor": 2.0, "max_drawdown": 0.25, "wf_score": 1.4},
            {"strategy": "rsi_reversion", "score": 1.1, "profit_factor": 1.6, "max_drawdown": 0.30, "wf_score": 1.0},
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        path = fh.name
    try:
        text = strategy_of_the_week(path)
    finally:
        os.unlink(path)

    assert "Strategy of the Week" in text
    assert "ema_cross" in text          # champion name
    assert "2.00" in text               # profit factor
    assert "25.0%" in text              # max drawdown
    assert "rsi_reversion" in text      # runner-up listed
    assert "fast=10" in text            # params rendered
    print("  strategy_of_the_week OK")


def test_audit_matched_within_tolerance():
    from src.monitoring.audit import audit_executions

    expected = [_trade("2026-05-30T10:00:00", "long", 100.0)]
    actual = [_trade("2026-05-30T10:00:01", "long", 100.10)]
    res = audit_executions(expected, actual, price_tolerance=0.25)
    assert res["num_matched"] == 1
    assert res["num_flagged"] == 0, res
    assert res["num_missing"] == 0 and res["num_extra"] == 0
    print("  audit matched within tolerance OK")


def test_audit_excessive_slippage_sign():
    from src.monitoring.audit import audit_executions

    # Long paying MORE than expected -> adverse -> positive slippage.
    expected = [_trade("2026-05-30T10:00:00", "long", 100.0)]
    actual = [_trade("2026-05-30T10:00:00", "long", 102.0)]
    res = audit_executions(expected, actual, price_tolerance=0.25)
    finding = next(f for f in res["findings"] if f["type"] == "matched")
    assert finding["flagged"] is True
    assert finding["slippage_exceeded"] is True
    assert abs(finding["slippage"] - 2.0) < 1e-9, finding  # positive = adverse
    assert res["num_flagged"] == 1
    assert abs(res["max_slippage"] - 2.0) < 1e-9

    # Short selling for LESS than expected -> adverse -> positive slippage.
    exp_s = [_trade("2026-05-30T10:00:00", "short", 100.0)]
    act_s = [_trade("2026-05-30T10:00:00", "short", 98.0)]
    res_s = audit_executions(exp_s, act_s, price_tolerance=0.25)
    f_s = next(f for f in res_s["findings"] if f["type"] == "matched")
    assert abs(f_s["slippage"] - 2.0) < 1e-9, f_s
    print("  audit excessive slippage + sign OK")


def test_audit_missing_and_extra():
    from src.monitoring.audit import audit_executions

    # Expected with no actual -> missing.
    res_missing = audit_executions([_trade("2026-05-30T10:00:00", "long", 100.0)], [])
    assert res_missing["num_missing"] == 1, res_missing
    assert res_missing["num_matched"] == 0

    # Actual with no expected -> extra.
    res_extra = audit_executions([], [_trade("2026-05-30T10:00:00", "long", 100.0)])
    assert res_extra["num_extra"] == 1, res_extra
    assert res_extra["num_matched"] == 0
    print("  audit missing / extra OK")


def test_audit_summary_stats():
    from src.monitoring.audit import audit_executions, audit_report

    expected = [
        _trade("2026-05-30T10:00:00", "long", 100.0, qty=2.0),
        _trade("2026-05-30T11:00:00", "short", 200.0, qty=1.0),
    ]
    actual = [
        _trade("2026-05-30T10:00:01", "long", 101.0, qty=2.0),   # +1 adverse
        _trade("2026-05-30T11:00:01", "short", 200.0, qty=1.0),  # 0 slip
        _trade("2026-05-30T12:00:00", "long", 50.0, qty=1.0),    # extra
    ]
    res = audit_executions(expected, actual, price_tolerance=0.25)
    assert res["num_matched"] == 2
    assert res["num_extra"] == 1
    assert res["num_missing"] == 0
    assert abs(res["avg_slippage"] - 0.5) < 1e-9, res          # (1.0 + 0.0)/2
    assert abs(res["max_slippage"] - 1.0) < 1e-9, res
    assert abs(res["total_slippage_cost"] - 2.0) < 1e-9, res    # 1.0 slip * 2 qty
    # extra counts as flagged; the +1 slippage trade flagged too.
    assert res["num_flagged"] == 1  # only matched-trade flags counted here
    report = audit_report(res)
    assert "Execution Audit" in report
    print("  audit summary stats OK")


def test_console_notifier_and_factory():
    from src.monitoring.notifier import ConsoleNotifier, Notifier, make_notifier

    n = ConsoleNotifier()
    assert n.send("hello") is True
    assert isinstance(n, Notifier)

    made = make_notifier("console")
    assert isinstance(made, ConsoleNotifier)
    assert made.send("via factory") is True

    # Default is console.
    default = make_notifier()
    assert isinstance(default, ConsoleNotifier)

    # Unknown kind falls back to console.
    fallback = make_notifier("smoke-signals")
    assert isinstance(fallback, ConsoleNotifier)

    # Unconfigured discord/telegram degrade gracefully (no network).
    from src.monitoring.notifier import DiscordNotifier, TelegramNotifier

    assert DiscordNotifier().send("x") is False
    assert TelegramNotifier().send("x") is False
    print("  console notifier + factory OK")


def test_loaders_roundtrip():
    from src.monitoring.trade_log import load_executions_csv, load_trades_json

    csv_text = (
        "Time,Instrument,Action,Quantity,Price\n"
        "2026-05-30 10:00:00,ES,Buy,2,100.25\n"
        "2026-05-30 11:00:00,ES,SellShort,1,200.50\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        fh.write(csv_text)
        csv_path = fh.name

    json_payload = {
        "trades": [
            {"timestamp": "2026-05-30T10:00:00", "symbol": "ES", "side": "long",
             "quantity": 1, "entry_price": 100.0, "exit_price": 105.0},
        ]
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(json_payload, fh)
        json_path = fh.name

    try:
        csv_trades = load_executions_csv(csv_path)
        json_trades = load_trades_json(json_path)
    finally:
        os.unlink(csv_path)
        os.unlink(json_path)

    assert len(csv_trades) == 2
    assert csv_trades[0].side == "long" and csv_trades[0].quantity == 2.0
    assert csv_trades[1].side == "short" and abs(csv_trades[1].entry_price - 200.50) < 1e-9
    assert len(json_trades) == 1
    assert abs(json_trades[0].realized_pnl() - 5.0) < 1e-9
    print("  loaders roundtrip OK")


if __name__ == "__main__":
    tests = [
        test_daily_stats_and_report,
        test_strategy_of_the_week,
        test_audit_matched_within_tolerance,
        test_audit_excessive_slippage_sign,
        test_audit_missing_and_extra,
        test_audit_summary_stats,
        test_console_notifier_and_factory,
        test_loaders_roundtrip,
    ]
    for t in tests:
        t()
    print(f"{len(tests)} tests passed.")
