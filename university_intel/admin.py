"""Telegram admin command listener for University Intelligence.

Uses the SAME bot token as the existing bot. This is safe because the existing
code never calls getUpdates (it only sends messages). All commands are
restricted to ADMIN_CHAT_IDS.

Commands:
  /adduniversity <name> <website> [state] [city]
  /removeuniversity <name>
  /listuniversities
  /forcescan
  /scan <name>          (scan a single university now)
  /stats
  /help
"""

from __future__ import annotations

import asyncio
import logging

from university_intel.config import ADMIN_CHAT_IDS, BOT_TOKEN, COMMAND_POLL_SECONDS
from university_intel.db import (
    add_university,
    add_source,
    find_university,
    list_universities,
    remove_university,
    stats,
)
from university_intel.http import AsyncHttp
from university_intel.models import Source, University
from university_intel.scanner import run_scan, scan_university
from university_intel.dedupe import Deduplicator

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
SUPPORTED_STATES = ("telangana",)


async def _api(http: AsyncHttp, method: str, **payload) -> dict:
    async with http.session.post(
        _API.format(token=BOT_TOKEN, method=method), json=payload, timeout=30
    ) as resp:
        return await resp.json()


async def _reply(http: AsyncHttp, chat_id: int, text: str) -> None:
    await _api(http, "sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
               disable_web_page_preview=True)


def _is_admin(chat_id: int) -> bool:
    # Commands only work when ADMIN_CHAT_IDS is configured and chat is listed.
    return bool(ADMIN_CHAT_IDS) and chat_id in ADMIN_CHAT_IDS


async def _handle_add(http: AsyncHttp, chat_id: int, args: list[str]) -> str:
    if len(args) < 2:
        return "Usage: /adduniversity <name> <website> [state] [city]\nExample: /adduniversity \"Osmania University\" https://osmania.ac.in Telangana Hyderabad"
    name = args[0]
    website = args[1]
    state = args[2] if len(args) > 2 else "Telangana"
    city = args[3] if len(args) > 3 else None
    if state.strip().lower() not in SUPPORTED_STATES:
        return f"State '{state}' is not supported yet. Supported: {', '.join(SUPPORTED_STATES)}"
    if not website.lower().startswith(("http://", "https://")):
        website = "https://" + website
    if find_university(name):
        return f"'{name}' is already registered."
    uid = add_university(
        University(id=None, name=name, state=state, city=city, website=website)
    )
    # Register the homepage as a generic source so a scan always has something.
    add_source(
        Source(university_id=uid, source_type="generic_page", url=website)
    )
    return (
        f"Added '{name}' (id={uid}).\n"
        f"State: {state}\nWebsite: {website}\n\n"
        "Run /forcescan to discover its event/RSS pages automatically."
    )


async def _handle_remove(chat_id: int, args: list[str]) -> str:
    if not args:
        return "Usage: /removeuniversity <name>"
    univ = find_university(" ".join(args))
    if not univ:
        return f"No university named '{' '.join(args)}' found."
    remove_university(univ.id)
    return f"Removed '{univ.name}' (id={univ.id})."


def _handle_list() -> str:
    universities = list_universities()
    if not universities:
        return "No universities registered yet. Use /adduniversity."
    lines = [f"<b>{len(universities)} university(s):</b>"]
    for u in universities:
        status = "✅" if u.active else "⏸️"
        lines.append(
            f"{status} <b>{u.name}</b> ({u.city or u.state})\n"
            f"   <a href=\"{u.website}\">website</a> | last scan: {u.last_scan or 'never'}"
        )
    return "\n".join(lines)


def _handle_stats() -> str:
    s = stats()
    by_cat = ", ".join(f"{k}: {v}" for k, v in list(s["by_category"].items())[:6])
    return (
        f"<b>University Intelligence stats</b>\n"
        f"Active universities: {s['universities']}\n"
        f"Registered sources: {s['sources']}\n"
        f"Events stored: {s['events']} (posted: {s['posted']})\n"
        f"Last scan: {s['last_scan'] or 'never'}\n"
        f"Top categories: {by_cat or '—'}"
    )


async def _handle_force_scan(chat_id: int) -> str:
    report = await run_scan(publish=True)
    return (
        f"Forced scan complete.\n"
        f"Universities: {report['universities']} | New: {report['new']} | "
        f"Duplicates: {report['duplicates']} | Filtered: {report['filtered']} | "
        f"Published: {report['published']}"
    )


async def _handle_scan_one(chat_id: int, args: list[str]) -> str:
    if not args:
        return "Usage: /scan <name>"
    univ = find_university(" ".join(args))
    if not univ:
        return f"No university named '{' '.join(args)}' found."
    http = AsyncHttp()
    await http.start()
    try:
        report = await scan_university(univ, http, Deduplicator(), publish=True)
    finally:
        await http.close()
    return (
        f"Scanned '{univ.name}'.\n"
        f"New: {report['new']} | Duplicates: {report['duplicates']} | "
        f"Filtered: {report['filtered']} | Published: {report['published']}"
    )


async def _handle_update(http: AsyncHttp, update: dict) -> None:
    message = update.get("message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if not text or not text.startswith("/"):
        return
    if not _is_admin(chat_id):
        if not ADMIN_CHAT_IDS:
            await _reply(
                http,
                chat_id,
                "⚠️ Admin commands are disabled. Set ADMIN_CHAT_IDS in .env.",
            )
        else:
            await _reply(http, chat_id, "⛔ You are not authorized to use these commands.")
        return

    parts = text.split()
    cmd = parts[0].split("@")[0].lower()
    args = parts[1:]
    handlers = {
        "/adduniversity": lambda: _handle_add(http, chat_id, args),
        "/removeuniversity": lambda: _handle_remove(chat_id, args),
        "/listuniversities": lambda: _handle_list(),
        "/stats": lambda: _handle_stats(),
        "/forcescan": lambda: _handle_force_scan(chat_id),
        "/scan": lambda: _handle_scan_one(chat_id, args),
        "/help": lambda: (
            "/adduniversity <name> <website> [state] [city]\n"
            "/removeuniversity <name>\n"
            "/listuniversities\n"
            "/scan <name>\n"
            "/forcescan\n"
            "/stats"
        ),
    }
    handler = handlers.get(cmd)
    if not handler:
        return
    try:
        result = await handler()
    except Exception as exc:
        logger.exception("command %s failed", cmd)
        result = f"⚠️ Command failed: {exc}"
    await _reply(http, chat_id, result)


async def run_command_listener() -> None:
    """Long-poll getUpdates using the shared token. Never raises out of the loop."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set — command listener disabled.")
        return
    if not ADMIN_CHAT_IDS:
        logger.warning(
            "ADMIN_CHAT_IDS is empty — commands will be disabled. "
            "Set ADMIN_CHAT_IDS (comma-separated numeric chat ids) in .env to enable."
        )
    http = AsyncHttp()
    await http.start()
    offset = 0
    logger.info("Command listener started (polling getUpdates).")
    try:
        while True:
            try:
                data = await _api(
                    http,
                    "getUpdates",
                    offset=offset,
                    timeout=COMMAND_POLL_SECONDS,
                    allowed_updates=["message"],
                )
                if not data.get("ok"):
                    logger.error("getUpdates error: %s", data.get("description"))
                    await asyncio.sleep(COMMAND_POLL_SECONDS)
                    continue
                for update in data.get("result", []):
                    offset = max(offset, update.get("update_id", 0) + 1)
                    try:
                        await _handle_update(http, update)
                    except Exception:
                        logger.exception("failed handling update")
            except Exception:
                logger.exception("command listener error")
                await asyncio.sleep(COMMAND_POLL_SECONDS)
    finally:
        await http.close()
