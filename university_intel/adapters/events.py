"""Listing-page adapters: events, news, announcements, innovation pages.

These crawl an official university page that lists announcements/events, visit
the promising linked pages to extract a title, snippet and date, and return
them as RawItems. Only same-site, public, non-navigation links are followed.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from university_intel.adapters.base import (
    RawItem,
    SourceAdapter,
    collect_page_links,
    _extract_dates,
    _extract_meta,
    normalize_title,
)
from university_intel.config import MAX_LINKS_PER_PAGE
from university_intel.http import AsyncHttp

logger = logging.getLogger(__name__)

# URL/path fragments that mark an announcement/event detail page.
_DETAIL_RE = re.compile(
    r"(event|hackathon|workshop|seminar|conference|symposi|tech[-_]?fest|fest|"
    r"contest|competition|challenge|bootcamp|ideathon|innovation|incubation|"
    r"startup|entrepreneur|training|notice|announcement|circular|news|update|"
    r"webinar|summit|meetup|lecture)",
    re.IGNORECASE,
)

_KEYWORD_SETS: dict[str, tuple[str, ...]] = {
    "events_page": (
        "event", "hackathon", "workshop", "seminar", "conference", "symposium",
        "techfest", "tech-fest", "fest", "contest", "competition", "challenge",
        "bootcamp", "ideathon", "innovation", "startup", "webinar", "summit",
    ),
    "innovation_page": (
        "innovation", "incubation", "startup", "entrepreneur", "hackathon",
        "ideathon", "cell", "iic", "e-cell",
    ),
    "news_page": (
        "news", "announcement", "notice", "update", "circular",
    ),
    "announcements_page": (
        "notice", "announcement", "circular", "update",
    ),
    "generic_page": (),
}

_DETAIL_CAP = {
    "events_page": 25,
    "innovation_page": 20,
    "news_page": 15,
    "announcements_page": 15,
    "generic_page": 0,
}

_ANCHOR_CAP = {
    "events_page": 0,
    "innovation_page": 0,
    "news_page": 40,
    "announcements_page": 40,
    "generic_page": 40,
}


class ListingPageAdapter(SourceAdapter):
    source_type = "events_page"

    @property
    def keywords(self) -> tuple[str, ...]:
        return _KEYWORD_SETS[self.source_type]

    def _is_promising(self, url: str, anchor: str) -> bool:
        if not self.keywords:
            return False
        haystack = f"{urlparse(url).path.lower()} {anchor.lower()}"
        return any(k in haystack for k in self.keywords)

    async def _visit_detail(
        self, http: AsyncHttp, base: str, url: str, anchor: str
    ) -> RawItem | None:
        try:
            html = await http.fetch(url)
        except Exception:
            return None
        soup = BeautifulSoup(html, "html.parser")
        title, description = _extract_meta(soup)
        if not title:
            h1 = soup.find("h1")
            title = normalize_title(h1.get_text(" ", strip=True)) if h1 else ""
        if not title:
            title = normalize_title(anchor)
        if not title:
            return None
        dates = _extract_dates(soup)
        return RawItem(url=url, title=title, description=description, date=dates[0] if dates else None)

    async def scan(self, http: AsyncHttp, source_url: str) -> list[RawItem]:
        html = await http.fetch(source_url)
        links = collect_page_links(http, source_url, html)
        if len(links) > MAX_LINKS_PER_PAGE:
            links = links[:MAX_LINKS_PER_PAGE]

        soup = BeautifulSoup(html, "html.parser")
        anchors = {}
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(" ", strip=True)
            anchors[href] = text
            resolved = http.absolute_url(source_url, href)
            if resolved:
                anchors[resolved] = text

        promising = [l for l in links if self._is_promising(l, anchors.get(l, ""))]
        rest = [l for l in links if not self._is_promising(l, anchors.get(l, ""))]

        items: list[RawItem] = []
        detail_cap = _DETAIL_CAP[self.source_type]
        for url in promising[:detail_cap]:
            item = await self._visit_detail(http, source_url, url, anchors.get(url, ""))
            if item:
                items.append(item)

        anchor_cap = _ANCHOR_CAP[self.source_type]
        for url in rest[:anchor_cap]:
            title = normalize_title(anchors.get(url, ""))
            if not title or len(title) < 12:
                continue
            items.append(RawItem(url=url, title=title))

        return items


class EventsPageAdapter(ListingPageAdapter):
    source_type = "events_page"


class InnovationPageAdapter(ListingPageAdapter):
    source_type = "innovation_page"


class NewsPageAdapter(ListingPageAdapter):
    source_type = "news_page"


class AnnouncementsPageAdapter(ListingPageAdapter):
    source_type = "announcements_page"


class GenericPageAdapter(ListingPageAdapter):
    source_type = "generic_page"
