"""
Module 3 (Risk Layer): daily drawdown guard.

Maps to spec: "If ... the account reaches within 20% of max daily drawdown,
automatically reduce position size by 50%."

Interpretation: ``max_daily_drawdown`` is the configured loss limit (in dollars
or as a fraction -- the units just have to match ``day_pnl``). We trip the guard
once the day's loss has consumed >= (1 - buffer_frac) of that limit, i.e. once
we are within the final ``buffer_frac`` (default 20%) before hitting the limit.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("interstellar.risk.drawdown")


def within_drawdown_buffer(
    day_pnl: float,
    max_daily_drawdown: float,
    buffer_frac: float = 0.20,
) -> tuple[bool, float]:
    """Decide whether the day's loss is within the drawdown buffer.

    Args:
        day_pnl: Today's realized+unrealized PnL. Negative = a loss.
        max_daily_drawdown: The max daily loss limit (a positive number; same
            units as ``day_pnl``). Values <= 0 disable the guard.
        buffer_frac: Trip when loss >= (1 - buffer_frac) of the limit.

    Returns:
        ``(tripped, pct_of_limit_used)`` where ``pct_of_limit_used`` is the
        fraction of the limit the current loss has consumed (0.0 if in profit).
    """
    if max_daily_drawdown is None or max_daily_drawdown <= 0:
        # Guard disabled / misconfigured -> never trip.
        return False, 0.0

    loss = max(0.0, -float(day_pnl))  # only losses count; profits -> 0
    pct_used = loss / float(max_daily_drawdown)
    threshold = 1.0 - float(buffer_frac)
    tripped = pct_used >= threshold
    return tripped, pct_used


def read_account_state(path: str) -> dict[str, Any]:
    """Read live account numbers from a JSON file (e.g. account_state.json).

    Expected keys include ``day_pnl`` and ``max_daily_drawdown``. Returns ``{}``
    on any failure so the caller can fall back to configured defaults.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as exc:
        logger.warning("Could not read account state from %s: %s", path, exc)
        return {}
