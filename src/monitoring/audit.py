"""
Audit — execution audit (slippage / execution-issue detection) for Module 4.

Spec mapping
------------
"Include an audit routine comparing expected backtest trades to actual broker
 executions to detect slippage or execution issues."

:func:`audit_executions` matches expected backtest trades against actual broker
executions (by nearest timestamp within matching side), computes signed
slippage (positive = adverse to the trader), and flags missing fills, extra
fills, excessive slippage and quantity mismatches.  Everything is pure and
deterministic so it is fully unit-testable with in-memory lists.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .trade_log import Trade


def _signed_slippage(side: str, expected_price: float, actual_price: float) -> float:
    """Slippage signed so positive = adverse.

    For a long, paying *more* than expected is adverse (actual - expected).
    For a short, selling for *less* than expected is adverse (expected - actual).
    """
    if side.lower() == "short":
        return expected_price - actual_price
    return actual_price - expected_price


def audit_executions(
    expected_trades: Sequence[Trade],
    actual_trades: Sequence[Trade],
    price_tolerance: float = 0.25,
    qty_tolerance: float = 0.0,
) -> Dict:
    """Compare expected backtest trades to actual broker executions.

    Matching: each expected trade is paired with the nearest-in-time unused
    actual execution that has the same side.  Returns a structured dict with
    summary stats and a per-trade findings list.

    Slippage is signed so positive values are adverse to the trader.  A trade is
    flagged for slippage when ``abs(slippage) > price_tolerance``, and for
    quantity when ``abs(qty diff) > qty_tolerance``.
    """
    unmatched_actual = list(actual_trades)
    findings: List[Dict] = []

    slippages: List[float] = []
    total_slippage_cost = 0.0
    num_missing = 0
    num_flagged = 0

    for exp in expected_trades:
        # Find nearest unused actual with matching side.
        candidates = [a for a in unmatched_actual if a.side.lower() == exp.side.lower()]
        if not candidates:
            num_missing += 1
            findings.append(
                {
                    "type": "missing",
                    "expected_timestamp": exp.timestamp.isoformat(),
                    "side": exp.side,
                    "expected_price": exp.entry_price,
                    "expected_qty": exp.quantity,
                    "flagged": True,
                }
            )
            continue

        match = min(
            candidates,
            key=lambda a: abs((a.timestamp - exp.timestamp).total_seconds()),
        )
        unmatched_actual.remove(match)

        slippage = _signed_slippage(exp.side, exp.entry_price, match.entry_price)
        qty_diff = match.quantity - exp.quantity
        # Adverse slippage cost scales with quantity (use the smaller fill size).
        cost = max(slippage, 0.0) * min(exp.quantity, match.quantity)
        total_slippage_cost += cost
        slippages.append(slippage)

        slippage_flag = abs(slippage) > price_tolerance
        qty_flag = abs(qty_diff) > qty_tolerance
        flagged = slippage_flag or qty_flag
        if flagged:
            num_flagged += 1

        findings.append(
            {
                "type": "matched",
                "expected_timestamp": exp.timestamp.isoformat(),
                "actual_timestamp": match.timestamp.isoformat(),
                "side": exp.side,
                "expected_price": exp.entry_price,
                "actual_price": match.entry_price,
                "slippage": slippage,
                "expected_qty": exp.quantity,
                "actual_qty": match.quantity,
                "qty_diff": qty_diff,
                "slippage_exceeded": slippage_flag,
                "qty_mismatch": qty_flag,
                "flagged": flagged,
            }
        )

    # Anything left over among actuals had no expected counterpart.
    num_extra = len(unmatched_actual)
    for extra in unmatched_actual:
        findings.append(
            {
                "type": "extra",
                "actual_timestamp": extra.timestamp.isoformat(),
                "side": extra.side,
                "actual_price": extra.entry_price,
                "actual_qty": extra.quantity,
                "flagged": True,
            }
        )

    abs_slips = [abs(s) for s in slippages]
    avg_slippage = (sum(slippages) / len(slippages)) if slippages else 0.0
    max_slippage = max(abs_slips) if abs_slips else 0.0

    return {
        "num_expected": len(expected_trades),
        "num_actual": len(actual_trades),
        "num_matched": len(slippages),
        "num_missing": num_missing,
        "num_extra": num_extra,
        "num_flagged": num_flagged,
        "avg_slippage": avg_slippage,
        "max_slippage": max_slippage,
        "total_slippage_cost": total_slippage_cost,
        "price_tolerance": price_tolerance,
        "qty_tolerance": qty_tolerance,
        "findings": findings,
    }


def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def audit_report(audit_result: Dict) -> str:
    """Format the audit result as a human-readable summary."""
    lines = [
        "Execution Audit",
        "-" * 28,
        f"Expected:    {audit_result['num_expected']}",
        f"Actual:      {audit_result['num_actual']}",
        f"Matched:     {audit_result['num_matched']}",
        f"Missing:     {audit_result['num_missing']}",
        f"Extra:       {audit_result['num_extra']}",
        f"Flagged:     {audit_result['num_flagged']}",
        f"Avg slip:    {audit_result['avg_slippage']:+.4f}",
        f"Max slip:    {audit_result['max_slippage']:.4f}",
        f"Slip cost:   {_money(audit_result['total_slippage_cost'])}",
    ]

    flagged = [f for f in audit_result.get("findings", []) if f.get("flagged")]
    if flagged:
        lines.append("-" * 28)
        lines.append("Flagged trades:")
        for f in flagged[:10]:
            if f["type"] == "missing":
                lines.append(
                    f"  MISSING {f['side']} @ {f['expected_price']} "
                    f"({f['expected_timestamp']})"
                )
            elif f["type"] == "extra":
                lines.append(
                    f"  EXTRA {f['side']} @ {f['actual_price']} "
                    f"({f['actual_timestamp']})"
                )
            else:
                reasons = []
                if f.get("slippage_exceeded"):
                    reasons.append(f"slip {f['slippage']:+.4f}")
                if f.get("qty_mismatch"):
                    reasons.append(f"qty {f['qty_diff']:+g}")
                lines.append(
                    f"  {f['side']} exp {f['expected_price']} -> "
                    f"act {f['actual_price']} ({', '.join(reasons)})"
                )
    else:
        lines.append("No issues flagged.")
    return "\n".join(lines)
