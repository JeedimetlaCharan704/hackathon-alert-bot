"""Unstop hackathon scraper.

Unstop (unstop.com/hackathons) is heavily JS-driven and often requires
session/CSRF cookies for its API. We try the public search endpoint first and
fall back to generic anchor extraction from the HTML. If Unstop blocks us the
scraper logs a warning and returns nothing (the run continues).
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html, fetch_json

logger = logging.getLogger(__name__)

SOURCE = "unstop"
BASE = "https://unstop.com"
LISTING_URL = f"{BASE}/hackathons"
API_URL = f"{BASE}/api/public/opportunity/search-result"

_HACK_DETAIL_RE = re.compile(r"hackathon", re.IGNORECASE)


def _from_api_item(item):
    title = (item.get("title") or "").strip()
    url = item.get("seo_url")
    if not title or not url:
        return None
    return build_listing(
        title=title,
        url=url,
        source=SOURCE,
        location=_location(item),
        prize_text=_prize_text(item),
        deadline_text=item.get("end_date"),
    )


def _location(item):
    addr = item.get("address_with_country_logo") or {}
    city = addr.get("city") or ""
    state = addr.get("state") or ""
    country = ((addr.get("country") or {}).get("name")) or ""
    region = (item.get("region") or "").lower()
    if region == "online":
        return "Online"
    parts = [p for p in (city, state, country) if p]
    return ", ".join(parts) or None


def _prize_text(item):
    details = item.get("details") or ""
    if details:
        text = BeautifulSoup(details, "html.parser").get_text(" ", strip=True)
        sentence = _sentence(text, ("prize", "reward", "cash"))
        if sentence:
            return sentence
    return None


def _sentence(text, markers):
    for sentence in re.split(r"[.!?\n]+", text):
        if any(m in sentence.lower() for m in markers):
            return sentence.strip()
    return None


def _fetch_api():
    data = fetch_json(
        API_URL,
        params={"opportunity": "hackathons", "per_page": 30},
    )
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        items = payload.get("data") or payload.get("competition") or []
    else:
        items = payload or []
    return [l for l in (_from_api_item(i) for i in items if isinstance(i, dict)) if l]


def _fetch_anchor_fallback():
    html = fetch_html(LISTING_URL)
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if _HACK_DETAIL_RE.search(href):
            url = urljoin(BASE, href)
            title = a.get_text(" ", strip=True)
            if title and url not in seen:
                seen.add(url)
                listing = build_listing(title=title, url=url, source=SOURCE)
                if listing:
                    out.append(listing)
    return out


def fetch_unstop():
    """Return a list of unstop listings in the common schema."""
    try:
        listings = _fetch_api()
        if listings:
            logger.info("unstop: got %d from API", len(listings))
            return listings
        logger.warning("unstop: API returned nothing")
    except Exception as exc:
        logger.warning("unstop: API failed (%s)", exc)

    try:
        return _fetch_anchor_fallback()
    except Exception as exc:
        logger.warning(
            "unstop: HTML fallback failed (%s) - this source may be blocking scrapers",
            exc,
        )
        return []
