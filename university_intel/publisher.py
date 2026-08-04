"""Publish university events through the existing Telegram pipeline.

Reuses `telegram_sender.send_message` (the exact same posting code and bot
token as the existing bot) and records sends in the existing `sent_listings`
table via `database.mark_sent`, so the two pipelines never double-post.
"""

from __future__ import annotations

import html
import logging
import time

import database as main_bot_db  # existing bot's mark_sent store (write reuse)
from config import CHANNEL_IDS
from filters import route_channel
from telegram_sender import send_message

from university_intel.models import Event, University

logger = logging.getLogger(__name__)

_CATEGORY_ICONS = {
    "Hackathon": "💻",
    "Coding Contest": "🧑‍💻",
    "Ideathon": "💡",
    "Startup Challenge": "🚀",
    "Innovation Challenge": "🧪",
    "AI Competition": "🤖",
    "Research Competition": "🔬",
    "Workshop": "🛠️",
    "Bootcamp": "🎓",
    "Internship": "💼",
    "Grant": "💰",
    "Scholarship": "🏅",
    "Conference": "🎤",
    "Tech Fest": "🎪",
    "Other": "📢",
}


def format_event_message(event: Event, university: University) -> str:
    """Render an event as a Telegram message (same HTML style as the bot)."""

    def esc(value):
        return html.escape(str(value or ""), quote=False)

    icon = _CATEGORY_ICONS.get(event.category, "📢")
    lines = [
        f"{icon} {event.category.upper()} — UNIVERSITY",
        "",
        f"🏛️ {esc(university.name)}",
        f"📍 {esc(university.city or university.state)}",
        f"📅 {esc(event.date or 'Date not specified')}",
        f"🏷️ {esc(event.category)}",
        "",
    ]
    if event.description:
        snippet = " ".join(event.description.split())[:280]
        lines.append(f"📝 {esc(snippet)}")
        lines.append("")
    lines.append(f"🔗 <a href=\"{html.escape(event.url, quote=True)}\">Open announcement</a>")
    lines.append(f"📰 Source: {esc(event.source)}")
    return "\n".join(lines)


def _channel_for(university: University) -> str:
    """Route like the existing bot: Telangana -> telangana channel, else india."""
    listing = {
        "location": university.city or "",
        "country": "India",
        "is_telangana": university.state.strip().lower() == "telangana",
    }
    return route_channel(listing)


async def publish_event(event: Event, university: University) -> bool:
    """Send one event; returns True if published (newly posted this time)."""
    channel = _channel_for(university)
    chat_id = CHANNEL_IDS.get(channel)
    if not chat_id:
        logger.error("No chat_id configured for channel %r", channel)
        return False

    text = format_event_message(event, university)
    ok = await _to_thread(send_message, chat_id, text)
    if not ok:
        logger.error("Failed to send event: %s", event.url)
        return False

    try:
        main_bot_db.mark_sent(event.url, channel)
    except Exception:
        logger.warning("could not mark sent in main bot DB for %s", event.url)
    logger.info("Published [%s] %s -> %s", event.category, event.title, channel)
    return True


async def _to_thread(fn, *args, **kwargs):
    import asyncio

    return await asyncio.to_thread(fn, *args, **kwargs)


def timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
