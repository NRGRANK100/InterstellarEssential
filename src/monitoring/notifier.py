"""
Notifier — messaging abstraction for Module 4 (Monitoring System).

Spec mapping
------------
"Build a Discord or Telegram bot that reports daily trades, PnL, and win rate,
 plus weekly 'Strategy of the Week' optimization results."

The user has not committed to Discord vs Telegram, so this module provides a
*pluggable* notifier supporting both, plus a console fallback used as the
default and in tests.  All network / third-party imports (``requests``) are
lazy (imported inside methods) so importing this module and running the unit
tests never requires network access or optional packages.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("monitoring.notifier")


# --------------------------------------------------------------------------- #
# Abstract base
# --------------------------------------------------------------------------- #
class Notifier(ABC):
    """Abstract messaging channel.  Concrete impls must implement ``send``."""

    @abstractmethod
    def send(self, text: str) -> bool:
        """Send ``text``; return True on success, False on (graceful) failure."""
        raise NotImplementedError

    def send_markdown(self, text: str) -> bool:
        """Send markdown-formatted text.  Default: route through ``send``."""
        return self.send(text)


# --------------------------------------------------------------------------- #
# Console (always works — default + tests)
# --------------------------------------------------------------------------- #
class ConsoleNotifier(Notifier):
    """Prints messages to stdout.  Never fails; requires no configuration."""

    def send(self, text: str) -> bool:
        print(text)
        return True


# --------------------------------------------------------------------------- #
# Discord (webhook preferred, bot token optional)
# --------------------------------------------------------------------------- #
class DiscordNotifier(Notifier):
    """Posts to Discord.

    Prefers the simple webhook approach (``requests.post`` to ``webhook_url``).
    A ``bot_token`` + ``channel_id`` pair is accepted as an alternative path
    using the Discord REST API.  Degrades gracefully (returns False, logs) when
    unconfigured or when the HTTP request fails.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.channel_id = channel_id

    def send(self, text: str) -> bool:
        if self.webhook_url:
            return self._send_webhook(text)
        if self.bot_token and self.channel_id:
            return self._send_bot(text)
        logger.warning("DiscordNotifier not configured (no webhook_url or bot_token/channel_id).")
        return False

    def _send_webhook(self, text: str) -> bool:
        try:
            import requests  # lazy import — keeps module/tests network-free
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning("requests unavailable for Discord webhook: %s", exc)
            return False
        try:
            resp = requests.post(self.webhook_url, json={"content": text}, timeout=10)
            if resp.status_code in (200, 204):
                return True
            logger.warning("Discord webhook failed: HTTP %s", resp.status_code)
            return False
        except Exception as exc:
            logger.warning("Discord webhook request error: %s", exc)
            return False

    def _send_bot(self, text: str) -> bool:
        try:
            import requests  # lazy import
        except Exception as exc:  # pragma: no cover
            logger.warning("requests unavailable for Discord bot: %s", exc)
            return False
        url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages"
        headers = {"Authorization": f"Bot {self.bot_token}"}
        try:
            resp = requests.post(url, headers=headers, json={"content": text}, timeout=10)
            if resp.status_code in (200, 201):
                return True
            logger.warning("Discord bot post failed: HTTP %s", resp.status_code)
            return False
        except Exception as exc:
            logger.warning("Discord bot request error: %s", exc)
            return False


# --------------------------------------------------------------------------- #
# Telegram (Bot HTTP API)
# --------------------------------------------------------------------------- #
class TelegramNotifier(Notifier):
    """Sends messages via the Telegram Bot HTTP API ``sendMessage`` endpoint.

    Degrades gracefully (returns False, logs) when unconfigured or on failure.
    """

    API_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, text: str) -> bool:
        if not (self.bot_token and self.chat_id):
            logger.warning("TelegramNotifier not configured (need bot_token and chat_id).")
            return False
        try:
            import requests  # lazy import
        except Exception as exc:  # pragma: no cover
            logger.warning("requests unavailable for Telegram: %s", exc)
            return False
        url = self.API_TEMPLATE.format(token=self.bot_token)
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            logger.warning("Telegram sendMessage failed: HTTP %s", resp.status_code)
            return False
        except Exception as exc:
            logger.warning("Telegram request error: %s", exc)
            return False

    def send_markdown(self, text: str) -> bool:
        if not (self.bot_token and self.chat_id):
            logger.warning("TelegramNotifier not configured (need bot_token and chat_id).")
            return False
        try:
            import requests  # lazy import
        except Exception as exc:  # pragma: no cover
            logger.warning("requests unavailable for Telegram: %s", exc)
            return False
        url = self.API_TEMPLATE.format(token=self.bot_token)
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("Telegram request error: %s", exc)
            return False


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def make_notifier(kind: str = "console", **kwargs) -> Notifier:
    """Build a notifier by ``kind`` in {"console","discord","telegram"}.

    Missing kwargs fall back to environment variables:
      Discord  : DISCORD_WEBHOOK_URL, DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
      Telegram : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    Unknown kinds fall back to the console notifier.
    """
    kind = (kind or "console").lower()

    if kind == "discord":
        return DiscordNotifier(
            webhook_url=kwargs.get("webhook_url") or os.getenv("DISCORD_WEBHOOK_URL"),
            bot_token=kwargs.get("bot_token") or os.getenv("DISCORD_BOT_TOKEN"),
            channel_id=kwargs.get("channel_id") or os.getenv("DISCORD_CHANNEL_ID"),
        )
    if kind == "telegram":
        return TelegramNotifier(
            bot_token=kwargs.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=kwargs.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID"),
        )
    if kind != "console":
        logger.warning("Unknown notifier kind %r; falling back to console.", kind)
    return ConsoleNotifier()
