"""Devpost hackathon scraper.

Tries the documented JSON API first (devpost.com/api/hackathons), falls back
to HTML scraping of devpost.com/hackathons.
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import MAX_PAGES_PER_SOURCE
from sources.common import build_listing, fetch_html, fetch_json

logger = logging.getLogger(__name__)

SOURCE = "devpost"
BASE = "https://devpost.com"
API_URL = f"{BASE}/api/hackathons"


def _from_api_item(item):
    title = (item.get("title") or "").strip()
    url = item.get("url") or item.get("id")
    if not title or not url:
        return None
    if not url.startswith("http"):
        url = urljoin(BASE, url)

    location = item.get("displayed_location")
    if isinstance(location, dict):
        location = location.get("location")
    elif not location:
        location = item.get("who_can_apply")
        if isinstance(location, list):
            location = ", ".join(location)

    prize = item.get("prize_amount")
    if prize:
        prize = re.sub(r"<[^>]+>", "", str(prize)).strip() or None

    return build_listing(
        title=title,
        url=url,
        source=SOURCE,
        location=location,
        prize_text=prize,
        deadline_text=item.get("submission_period_dates"),
        tags=[t.get("name") for t in (item.get("themes") or []) if isinstance(t, dict)],
    )


def _fetch_api():
    listings = []
    for page in range(1, MAX_PAGES_PER_SOURCE + 1):
        data = fetch_json(API_URL, params={"status": "upcoming", "page": page})
        items = data.get("hackathons") or []
        if not items:
            break
        listings.extend(_from_api_item(i) for i in items)
    return [l for l in listings if l]


def _fetch_html():
    html = fetch_html(urljoin(BASE, "/hackathons"))
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for card in soup.select("div.challenge-content, div.challenge"):
        link = card.find("a", class_="challenge-title")
        if not link:
            continue
        title = link.get_text(strip=True)
        url = urljoin(BASE, link.get("href", ""))
        location = card.select_one(".challenge-location, .challenge-open-to")
        prize = card.select_one(".prize_amount, .challenge-prize, .challenge-statistic")
        deadline = card.select_one(".submission-period, .challenge-submission, .challenge-deadline")
        listing = build_listing(
            title=title,
            url=url,
            source=SOURCE,
            location=location.get_text(" ", strip=True) if location else None,
            prize_text=prize.get_text(" ", strip=True) if prize else None,
            deadline_text=deadline.get_text(" ", strip=True) if deadline else None,
        )
        if listing:
            listings.append(listing)
    return listings


def fetch_devpost():
    """Return a list of devpost listings in the common schema."""
    try:
        listings = _fetch_api()
        if listings:
            logger.info("devpost: got %d from JSON API", len(listings))
            return listings
        logger.warning("devpost: JSON API returned nothing, falling back to HTML")
    except Exception as exc:
        logger.warning("devpost: JSON API failed (%s), falling back to HTML", exc)
    return _fetch_html()
