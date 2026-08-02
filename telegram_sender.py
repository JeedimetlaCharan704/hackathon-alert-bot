"""Telegram message formatting + sending via the raw Bot API.

Uses parse_mode=HTML (only needs <>& escaped, far less error-prone than
MarkdownV2 with emoji in the message).
"""

import html
import logging

import requests

from config import BOT_TOKEN

logger = logging.getLogger(__name__)

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def format_message(listing: dict) -> str:
    """Render a listing as a Telegram message (HTML parse mode)."""

    def esc(value):
        return html.escape(str(value or "Not specified"), quote=False)

    lines = [
        "🚀 NEW HACKATHON",
        "",
        f"📍 Location: {esc(listing.get('location'))}",
        f"🏆 Prize: {esc(listing.get('raw_prize_text'))}",
        f"🎯 Tags: {esc(', '.join(listing.get('tags') or []))}",
        f"📅 Deadline: {esc(listing.get('deadline'))}",
        "",
        f"🔗 Apply: <a href=\"{html.escape(listing['url'], quote=True)}\">Open listing</a>",
        f"📰 Source: {esc(listing.get('source'))}",
    ]
    return "\n".join(lines)


def send_message(chat_id: str, text: str) -> bool:
    """POST a message to a Telegram chat. Returns True on success."""
    if not chat_id:
        logger.error("No chat_id configured - check the %s channel env var", "channel")
        return False
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set")
        return False
    try:
        resp = requests.post(
            _API_URL.format(token=BOT_TOKEN),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.error(
                "Telegram API error: %s (chat_id=%s)", data.get("description"), chat_id
            )
            return False
        return True
    except Exception:
        logger.exception("Failed to send Telegram message to %s", chat_id)
        return False
