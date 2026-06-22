"""
Robinhood brokerage client (equities) built on `robin_stocks`.

Thin, testable wrapper around the parts of robin_stocks the pipeline needs:
  * login (TOTP-friendly)
  * historical bars -> the pipeline's canonical OHLCV schema
  * latest price
  * positions / buying power
  * market buy/sell by quantity

`robin_stocks` is imported lazily inside `login()` so importing this module
(and running the test suite) never requires the package or a network/login.

Safety: pass `dry_run=True` to place no real orders — the client logs the
intended order and returns a synthetic ack. The connector defaults to live
trading (per project decision) but every order path honors this flag.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from src.optimizer.data import CANONICAL_COLS

log = logging.getLogger("broker.client")


class BrokerError(RuntimeError):
    """Raised for connector-level failures (login, order rejects, etc.)."""


# robin_stocks interval/span pairs we support, mapped to a canonical key.
_INTERVAL_SPAN = {
    "5minute": "week",
    "10minute": "week",
    "hour": "month",
    "day": "year",
}


@dataclass
class RobinhoodClient:
    """Equities connector. `api` is injectable so tests can pass a fake."""

    username: str | None = None
    password: str | None = None
    mfa_code: str | None = None          # TOTP secret or current code
    dry_run: bool = False
    api: object = None                   # robin_stocks.robinhood module (or a fake)
    _logged_in: bool = field(default=False, init=False)

    # ── auth ────────────────────────────────────────────────────────────
    def login(self) -> None:
        """Authenticate. Reads creds from env if not supplied."""
        if self.api is None:
            try:
                import robin_stocks.robinhood as rh  # lazy: not needed for import/tests
            except ImportError as exc:  # pragma: no cover - env-dependent
                raise BrokerError(
                    "robin_stocks is not installed. `pip install robin_stocks`."
                ) from exc
            self.api = rh

        user = self.username or os.getenv("ROBINHOOD_USERNAME")
        pw = self.password or os.getenv("ROBINHOOD_PASSWORD")
        mfa = self.mfa_code or os.getenv("ROBINHOOD_MFA")
        if not user or not pw:
            raise BrokerError("Robinhood credentials missing (set ROBINHOOD_USERNAME/PASSWORD).")

        kwargs = {}
        if mfa:
            # if it's a TOTP secret, derive the current code
            kwargs["mfa_code"] = _totp_now(mfa)
        try:
            self.api.login(user, pw, **kwargs)
        except Exception as exc:  # pragma: no cover - network
            raise BrokerError(f"Robinhood login failed: {exc}") from exc
        self._logged_in = True
        log.info("Robinhood login OK (dry_run=%s)", self.dry_run)

    def _require_login(self) -> None:
        if not self._logged_in and self.api is None:
            raise BrokerError("Not logged in. Call login() first.")

    # ── market data ─────────────────────────────────────────────────────
    def get_history(self, symbol: str, interval: str = "5minute") -> pd.DataFrame:
        """Return canonical OHLCV bars (open/high/low/close/volume, dt index)."""
        self._require_login()
        span = _INTERVAL_SPAN.get(interval, "week")
        try:
            raw = self.api.get_stock_historicals(symbol, interval=interval, span=span)
        except Exception as exc:  # pragma: no cover - network
            raise BrokerError(f"history fetch failed for {symbol}: {exc}") from exc
        return _historicals_to_df(raw)

    def get_price(self, symbol: str) -> float:
        self._require_login()
        try:
            px = self.api.get_latest_price(symbol)
        except Exception as exc:  # pragma: no cover - network
            raise BrokerError(f"price fetch failed for {symbol}: {exc}") from exc
        if not px or px[0] is None:
            raise BrokerError(f"no price for {symbol}")
        return float(px[0])

    # ── account ─────────────────────────────────────────────────────────
    def get_position_qty(self, symbol: str) -> float:
        """Net share quantity held for `symbol` (0 if flat). Robinhood is long-only."""
        self._require_login()
        try:
            positions = self.api.get_open_stock_positions()
        except Exception as exc:  # pragma: no cover - network
            raise BrokerError(f"positions fetch failed: {exc}") from exc
        for p in positions or []:
            sym = self._symbol_for_position(p)
            if sym == symbol:
                return float(p.get("quantity", 0.0))
        return 0.0

    def buying_power(self) -> float:
        self._require_login()
        try:
            prof = self.api.load_account_profile()
            return float(prof.get("buying_power", 0.0))
        except Exception as exc:  # pragma: no cover - network
            raise BrokerError(f"buying power fetch failed: {exc}") from exc

    def _symbol_for_position(self, p: dict) -> str | None:
        if p.get("symbol"):
            return p["symbol"]
        url = p.get("instrument")
        if url and hasattr(self.api, "get_instrument_by_url"):
            try:
                return self.api.get_instrument_by_url(url).get("symbol")
            except Exception:  # pragma: no cover - network
                return None
        return None

    # ── orders ──────────────────────────────────────────────────────────
    def market_buy(self, symbol: str, quantity: float) -> dict:
        return self._order(symbol, quantity, "buy")

    def market_sell(self, symbol: str, quantity: float) -> dict:
        return self._order(symbol, quantity, "sell")

    def _order(self, symbol: str, quantity: float, side: str) -> dict:
        if quantity <= 0:
            return {"state": "skipped", "reason": "non-positive quantity"}
        if self.dry_run:
            log.info("[DRY-RUN] %s %s x%s", side.upper(), symbol, quantity)
            return {
                "id": "dry-run",
                "state": "dry_run",
                "side": side,
                "symbol": symbol,
                "quantity": quantity,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        self._require_login()
        fn = self.api.order_buy_market if side == "buy" else self.api.order_sell_market
        try:
            res = fn(symbol, quantity)
        except Exception as exc:  # pragma: no cover - network
            raise BrokerError(f"{side} order failed for {symbol}: {exc}") from exc
        if res is None or (isinstance(res, dict) and res.get("detail")):
            raise BrokerError(f"{side} order rejected for {symbol}: {res}")
        log.info("%s order placed: %s x%s -> %s",
                 side.upper(), symbol, quantity, res.get("id", "?"))
        return res


# ── helpers ─────────────────────────────────────────────────────────────


def _historicals_to_df(raw: list[dict]) -> pd.DataFrame:
    """robin_stocks historicals -> canonical OHLCV DataFrame."""
    if not raw:
        raise BrokerError("empty historicals")
    rows = []
    for bar in raw:
        rows.append({
            "datetime": pd.to_datetime(bar["begins_at"]),
            "open": float(bar["open_price"]),
            "high": float(bar["high_price"]),
            "low": float(bar["low_price"]),
            "close": float(bar["close_price"]),
            "volume": float(bar.get("volume", 0) or 0),
        })
    df = pd.DataFrame(rows).set_index("datetime").sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index.name = "datetime"
    return df[CANONICAL_COLS]


def _totp_now(secret_or_code: str) -> str:
    """If given a base32 TOTP secret, return the current 6-digit code; else passthrough."""
    code = secret_or_code.strip().replace(" ", "")
    # a 6-digit numeric string is already a code
    if code.isdigit() and len(code) == 6:
        return code
    try:
        import pyotp  # lazy optional dep
        return pyotp.TOTP(code).now()
    except Exception:
        # not a secret we can parse; hand it back and let login decide
        return secret_or_code
