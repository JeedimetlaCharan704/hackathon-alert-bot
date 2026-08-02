"""MLH hackathon scraper.

The old public JSON feed (mlh.io/seasons/*/events.json) was retired when MLH
moved to mlh.com. The current events page (https://mlh.io/events, which
redirects to the active season) embeds schema.org microdata - each event is an
<a itemscope itemtype="schema.org/Event"> with meta start/end dates, an
attendance mode (online vs in-person) and a postal address. We parse that.

MLH doesn't publish prize amounts, so listings carry prize_value=None (they
still alert while PASS_UNKNOWN_PRIZE is on).
"""

import logging
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html, fetch_json

logger = logging.getLogger(__name__)

SOURCE = "mlh"
SEASON_PAGE = "https://mlh.io/events"
LEGACY_FEED = "https://mlh.io/seasons/2026/events.json"


def _clean_url(url: str) -> str:
    """Strip tracking query params (utm_*) from a URL."""
    parsed = urlparse(url)
    keep = {k: v for k, v in parse_qs(parsed.query).items() if not k.startswith("utm_")}
    if keep:
        parsed = parsed._replace(query=urlencode(keep, doseq=True))
    else:
        parsed = parsed._replace(query="")
    return urlunparse(parsed)


def _event_location(a):
    mode = a.find("meta", itemprop="eventAttendanceMode")
    if mode and "Online" in (mode.get("content") or ""):
        return "Online"

    name_el = a.select_one('div[itemprop="location"] span[itemprop="name"]')
    locality = a.find("meta", itemprop="addressLocality")
    region = a.find("meta", itemprop="addressRegion")
    country = a.find("meta", itemprop="addressCountry")

    name = name_el.get_text(" ", strip=True) if name_el else ""
    parts = []
    for el in (locality, region, country):
        if el and el.get("content"):
            parts.append(el["content"])
    joined = ", ".join(p for p in parts if p)
    return name if name and not joined else joined or name or None


def _fetch_html():
    html = fetch_html(SEASON_PAGE)
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    seen = set()

    for a in soup.find_all("a"):
        if not (a.get("itemscope") is not None and a.get("itemtype", "").endswith("/Event")):
            continue
        url = _clean_url(a.get("href", ""))
        title_el = a.find("h4")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not url or not title or url in seen:
            continue
        seen.add(url)

        start = a.find("meta", itemprop="startDate")
        end = a.find("meta", itemprop="endDate")
        deadline = (end or start).get("content") if (end or start) else None

        listing = build_listing(
            title=title,
            url=url,
            source=SOURCE,
            location=_event_location(a),
            deadline_text=deadline,
        )
        if listing:
            listings.append(listing)
    return listings


def _fetch_legacy_feed():
    data = fetch_json(LEGACY_FEED)
    listings = []
    seen = set()
    for event in data.get("data") or []:
        url = event.get("url")
        title = event.get("name")
        if not url or not title or url in seen:
            continue
        seen.add(url)
        listing = build_listing(
            title=title,
            url=url,
            source=SOURCE,
            location=event.get("location"),
            deadline_text=event.get("end-date"),
        )
        if listing:
            listings.append(listing)
    return listings


def fetch_mlh():
    """Return a list of MLH listings in the common schema."""
    try:
        listings = _fetch_html()
        if listings:
            logger.info("mlh: got %d from season page microdata", len(listings))
            return listings
        logger.warning("mlh: season page yielded no events")
    except Exception as exc:
        logger.warning("mlh: season page parse failed (%s)", exc)

    try:
        listings = _fetch_legacy_feed()
        if listings:
            logger.info("mlh: got %d from legacy JSON feed", len(listings))
            return listings
    except Exception as exc:
        logger.warning("mlh: legacy JSON feed unavailable (%s)", exc)
    return []
