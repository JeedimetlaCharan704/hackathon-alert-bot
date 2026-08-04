"""Automatic discovery of official public event/RSS/innovation pages.

Given a university homepage, this looks for:

* RSS/Atom feed <link> tags and conventional feed URLs (/feed, /rss.xml, ...)
* Event / news / announcements / innovation pages reachable from the homepage
* sitemap.xml (used to find more event pages later)

Discovered URLs are stored in the `sources` table (discovered=1) so future
scans reuse them. It only follows same-host links on the homepage — it never
scrapes private areas and never exceeds polite per-request delays.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from university_intel.config import ENABLE_DISCOVERY, MAX_LINKS_PER_PAGE
from university_intel.db import add_source
from university_intel.http import AsyncHttp
from university_intel.models import Source, University

logger = logging.getLogger(__name__)

_FEED_PATHS = ("/feed", "/feeds", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/rss/index.xml")
_SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/sitemapindex.xml")

_PAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "events_page": ("events", "event", "campus-events", "whats-on"),
    "innovation_page": (
        "innovation", "incubation", "startup", "e-cell", "ecell", "iic",
        "entrepreneurship", "technology-transfer",
    ),
    "news_page": ("news", "notices", "announcements", "updates"),
    "announcements_page": ("notices", "announcements", "circulars", "bulletin"),
}


async def _first_available(urls: list[str], http: AsyncHttp) -> str | None:
    """Return the first URL that fetches successfully (polite GET probe)."""
    for url in urls:
        try:
            await http.fetch(url)
        except Exception:
            continue
        return url
    return None


async def discover(homepage: str, http: AsyncHttp) -> dict[str, str]:
    """Discover rss_url / events_url / innovation_url / news_url for a homepage."""
    found: dict[str, str] = {}
    try:
        html = await http.fetch(homepage)
    except Exception:
        logger.warning("discovery: could not fetch %s", homepage)
        return found

    base = homepage
    soup = BeautifulSoup(html, "html.parser")
    links = list(
        {
            url
            for a in soup.find_all("a", href=True)
            if (url := urljoin(base, a["href"].strip()))
            and url.lower().startswith(("http://", "https://"))
            and urlparse(url).netloc == urlparse(base).netloc
        }
    )[:MAX_LINKS_PER_PAGE]

    # --- RSS / Atom feeds -------------------------------------------------
    for rel in ("alternate",):
        for tag in soup.find_all("link", attrs={"rel": rel}):
            typ = (tag.get("type") or "").lower()
            href = (tag.get("href") or "").strip()
            if "rss" in typ or "atom" in typ or "xml" in typ:
                if href and not found.get("rss_url"):
                    found["rss_url"] = urljoin(base, href)
    if not found.get("rss_url"):
        probe = [urljoin(base, p) for p in _FEED_PATHS]
        hit = await _first_available(probe, http)
        if hit:
            found["rss_url"] = hit

    # --- event/innovation/news/announcement pages --------------------------
    page_pool: list[tuple[str, str]] = []  # (url, lowercase path)
    for url in links:
        path = urlparse(url).path.lower()
        if not path or path in ("/", "/index.html", "/index.php"):
            continue
        page_pool.append((url, path))

    for kind, keywords in _PAGE_KEYWORDS.items():
        if kind in found:
            continue
        for url, path in page_pool:
            if any(k in path for k in keywords):
                found[kind] = url
                break
        if kind == "innovation_page" and "innovation_url" not in found:
            # innovation cells often live under another host (e.g. iic.example)
            for url in links:
                path = urlparse(url).path.lower()
                if any(k in path for k in keywords) and not url.startswith(base):
                    found["innovation_url"] = url
                    break

    # --- sitemap -----------------------------------------------------------
    for path in _SITEMAP_PATHS:
        hit = await _first_available([urljoin(base, path)], http)
        if hit:
            found["sitemap_url"] = hit
            break

    return found


async def discover_and_store(university: University, http: AsyncHttp) -> int:
    """Run discovery for one university and persist new sources.

    Returns the number of new sources stored. Never raises (discovery failure
    is logged and ignored).
    """
    if not ENABLE_DISCOVERY:
        return 0
    if not university.id:
        return 0
    try:
        found = await discover(university.website, http)
    except Exception:
        logger.warning("discovery failed for %s", university.name, exc_info=True)
        return 0

    created = 0
    mapping = {
        "rss_url": "rss",
        "events_url": "events_page",
        "innovation_url": "innovation_page",
        "news_url": "news_page",
        "announcements_url": "announcements_page",
    }
    for field, source_type in mapping.items():
        url = found.get(field)
        if not url:
            continue
        if add_source(Source(university_id=university.id, source_type=source_type, url=url, discovered=True)):
            created += 1
            logger.info("discovered %s for %s: %s", source_type, university.name, url)
    sitemap_url = found.get("sitemap_url")
    if sitemap_url:
        try:
            xml = await http.fetch(sitemap_url)
            from university_intel.adapters.sitemap import _EVENTISH_RE, _parse_sitemap

            eventish = [
                u for u in _parse_sitemap(xml, sitemap_url) if _EVENTISH_RE.search(u)
            ][:3]
            for url in eventish:
                if add_source(
                    Source(
                        university_id=university.id,
                        source_type="events_page",
                        url=url,
                        discovered=True,
                    )
                ):
                    created += 1
                    logger.info(
                        "discovered events page from sitemap for %s: %s",
                        university.name,
                        url,
                    )
        except Exception:
            logger.warning("could not parse sitemap for %s", university.name, exc_info=True)
    return created
