"""Sitemap adapter — walks a university's sitemap.xml for event-like pages.

Also used by the discovery tool to find pages worth registering as sources.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from university_intel.adapters.base import RawItem, SourceAdapter, normalize_title
from university_intel.config import MAX_LINKS_PER_PAGE
from university_intel.http import AsyncHttp

logger = logging.getLogger(__name__)

_EVENTISH_RE = re.compile(
    r"(event|hackathon|workshop|seminar|conference|symposi|tech[-_]?fest|fest|"
    r"contest|competition|challenge|bootcamp|ideathon|innovation|incubation|"
    r"startup|entrepreneur|news|announcement|notice|circular|update)",
    re.IGNORECASE,
)


class SitemapAdapter(SourceAdapter):
    source_type = "sitemap"

    async def scan(self, http: AsyncHttp, source_url: str) -> list[RawItem]:
        xml = await http.fetch(source_url)
        urls = _parse_sitemap(xml, source_url)
        items: list[RawItem] = []
        for u in urls:
            if _EVENTISH_RE.search(u):
                items.append(RawItem(url=u, title="", description=""))
        return items[:MAX_LINKS_PER_PAGE]


def _parse_sitemap(xml: str, base_url: str) -> list[str]:
    """Parse a sitemap (or sitemap index) into absolute URLs."""
    soup = BeautifulSoup(xml, "xml")
    urls: list[str] = []
    for loc in soup.find_all("loc"):
        url = urljoin(base_url, loc.get_text(strip=True))
        if url.lower().startswith(("http://", "https://")):
            urls.append(url)
    return urls
