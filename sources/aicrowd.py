"""AIcrowd challenge scraper.

Parses the challenges listing page. Each active challenge is an <a> card whose
status text says things like "Phase 1: 4 days left" or "Round 2: Completed".
Only challenges that are still running are kept; the deadline is derived from
"X days/hours left". Prize amounts are on the detail page only, so
prize_value=None (alerts because aicrowd is in LIKELY_CASH_SOURCES).
"""

import datetime as _dt
import logging
import re

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html

logger = logging.getLogger(__name__)

SOURCE = "aicrowd"
LIST_URL = "https://www.aicrowd.com/challenges"

_DAYS_LEFT = re.compile(r"(\d+)\s*days?\s*left", re.IGNORECASE)
_HOURS_LEFT = re.compile(r"(\d+)\s*hours?\s*left", re.IGNORECASE)


def _is_done(text):
    t = text.lower()
    return any(w in t for w in ("completed", "ended", "closed", "finished"))


def _deadline_from(text):
    m = _DAYS_LEFT.search(text)
    if m:
        return (_dt.date.today() + _dt.timedelta(days=int(m.group(1)))).isoformat()
    m = _HOURS_LEFT.search(text)
    if m:
        return (_dt.date.today() + _dt.timedelta(hours=int(m.group(1)))).isoformat()
    return None


def _card_for(anchor, soup):
    """Walk up to the card container and return its text (status + title)."""
    node = anchor
    for _ in range(4):
        node = node.parent
        if node is None:
            break
        h = node.find(["h2", "h3", "h4"])
        if h:
            return node
    return None


def fetch_aicrowd():
    """Return a list of AIcrowd challenge listings in the common schema."""
    html = fetch_html(LIST_URL)
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    seen = set()
    for a in soup.find_all("a", href=lambda h: h and h.startswith("/challenges/")):
        if a["href"].count("/") != 2:
            continue
        url = f"https://www.aicrowd.com{a['href']}"
        if url in seen:
            continue
        seen.add(url)
        status_text = a.get_text(" ", strip=True)
        if _is_done(status_text):
            continue
        card = _card_for(a, soup)
        title = ""
        if card:
            h = card.find(["h2", "h3", "h4"])
            title = h.get_text(" ", strip=True) if h else ""
        if not title:
            title = a["href"].split("/")[-1].replace("-", " ").title()
        listing = build_listing(
            title=title,
            url=url,
            source=SOURCE,
            location="Online",
            deadline_text=_deadline_from(status_text),
            tags=["ai", "ml", "competition", "machine learning"],
        )
        if listing:
            listings.append(listing)
    return listings
