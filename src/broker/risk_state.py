"""
Tiny reader for the risk layer's shared state file.

The Robinhood connector consumes the exact same contract the generated
NinjaScript used: a JSON file containing a numeric ``risk_multiplier`` in
(0, 1.0]. Anything missing/invalid/out-of-range falls back to 1.0 so a bad
read can never *upsize* position — matching the NinjaScript fail-safe.
"""

from __future__ import annotations

import json
import logging

log = logging.getLogger("broker.risk_state")


def read_risk_multiplier(path: str, default: float = 1.0) -> float:
    """Return the risk multiplier from `path`, clamped to (0, 1.0]."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        m = float(data["risk_multiplier"])
    except FileNotFoundError:
        return default
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        log.warning("Bad risk_state at %s (%s); using %.2f", path, exc, default)
        return default
    # never upsize on a surprising value
    if not (0.0 < m <= 1.0):
        log.warning("risk_multiplier %.3f out of (0,1]; using %.2f", m, default)
        return default
    return m
