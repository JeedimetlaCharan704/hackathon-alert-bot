"""ETHGlobal hackathon/conference scraper.

Parses the events listing page (https://ethglobal.com/events). Each card is an
<a href="/events/<slug>"> with the title in an <h2>, the location + event type
in <span class="inline-flex ..."> chips, and the date in a month/day block.
Prize amounts are not shown on the listing page, so prize_value=None (alerts
because ethglobal is in LIKELY_CASH_SOURCES).
"""

import datetime as _dt
import logging
import re

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html

logger = logging.getLogger(__name__)

SOURCE = "ethglobal"
LIST_URL = "https://ethglobal.com/events"

_EVENT_LINK = re.compile(r"^/events/[a-z0-9-]+/?$")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _class_contains(el, name):
    if el is None:
        return False
    cls = el.get("class") or []
    if isinstance(cls, str):
        cls = [cls]
    return any(name in c for c in cls)


def _card_date(a):
    """Return (month, last_day) from the date block, or (None, None)."""
    month_el = a.find("div", class_=lambda c: c and "uppercase" in " ".join(c) if isinstance(c, list) else "uppercase" in (c or ""))
    days_el = a.find("div", class_=lambda c: c and "font-extrabold" in " ".join(c) if isinstance(c, list) else "font-extrabold" in (c or ""))
    month = month_el.get_text(strip=True) if month_el else ""
    month = month.split(" ")[0].strip().lower().rstrip(".")
    day_tokens = days_el.get_text(" ", strip=True).split() if days_el else []
    last_day = day_tokens[-1] if day_tokens else ""
    return month, last_day


def _deadline_text(a):
    month, last_day = _card_date(a)
    if not month or not last_day:
        return None
    try:
        m = _MONTHS[month[:3]]
        d = int(last_day)
    except (KeyError, ValueError):
        return None
    today = _dt.date.today()
    for year in (today.year, today.year + 1):
        try:
            date = _dt.date(year, m, d)
        except ValueError:
            continue
        if date >= today:
            return date.isoformat()
    return None


def _location_and_type(a):
    chips = [s.get_text(" ", strip=True) for s in a.find_all("span", class_="inline-flex")]
    chips = [c for c in chips if c and c not in ("Apply", "to", "Attend")]
    if not chips:
        return "Online", ""
    if len(chips) >= 2:
        return chips[0], chips[1]
    # single chip = event type (e.g. "Async Hackathon") -> online event
    return "Online", chips[0]


def fetch_ethglobal():
    """Return a list of ETHGlobal event listings in the common schema."""
    html = fetch_html(LIST_URL)
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    seen = set()
    for a in soup.find_all("a", href=_EVENT_LINK):
        url = f"https://ethglobal.com{a['href']}"
        if url in seen:
            continue
        seen.add(url)
        title_el = a.find("h2")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            continue
        location, event_type = _location_and_type(a)
        if event_type and "hackathon" not in event_type.lower() and "summit" not in event_type.lower():
            # conferences/coworking are not contests
            continue
        listing = build_listing(
            title=title,
            url=url,
            source=SOURCE,
            location=location,
            deadline_text=_deadline_text(a),
            tags=["hackathon", "web3", "blockchain"],
        )
        if listing:
            listings.append(listing)
    return listings
