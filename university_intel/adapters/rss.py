"""RSS / Atom feed adapter (official university feeds)."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import feedparser

from university_intel.adapters.base import RawItem, SourceAdapter, normalize_title
from university_intel.config import MAX_RSS_ENTRIES
from university_intel.http import AsyncHttp

logger = logging.getLogger(__name__)


class RssAdapter(SourceAdapter):
    source_type = "rss"

    async def scan(self, http: AsyncHttp, source_url: str) -> list[RawItem]:
        text = await http.fetch(source_url)
        feed = feedparser.parse(text)
        items: list[RawItem] = []
        for entry in feed.entries[:MAX_RSS_ENTRIES]:
            link = entry.get("link") or ""
            if not link:
                continue
            link = urljoin(source_url, link)
            title = normalize_title(entry.get("title") or "")
            if not title:
                continue
            description = normalize_title(entry.get("summary") or entry.get("description") or "")
            date = _iso_date(entry.get("published") or entry.get("updated"))
            items.append(RawItem(url=link, title=title, description=description, date=date))
        return items


def _iso_date(raw: str) -> str | None:
    """Parse an RFC-822/ISO date string to YYYY-MM-DD (best effort)."""
    if not raw:
        return None
    from email.utils import parsedate_to_datetime

    try:
        dt = parsedate_to_datetime(raw)
        return dt.date().isoformat()
    except (ValueError, TypeError):
        try:
            from datetime import datetime

            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return None
