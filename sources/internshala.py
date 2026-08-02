"""Internshala hackathon/competition scraper.

Internshala (internshala.com/competitions/hackathons) sometimes blocks bots
(HTTP 403). When reachable, its listing cards carry the title, a date line
(📅), a location line (📍) and a prize tag (🏆) which we parse here.
If it is blocked, we log a warning and skip - the run continues.
"""

import logging
import re

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html

logger = logging.getLogger(__name__)

SOURCE = "internshala"
BASE = "https://internshala.com"
LISTING_URL = f"{BASE}/competitions/hackathons"

_HACK_DETAIL_RE = re.compile(r"hackathon", re.IGNORECASE)


def _parse_byline(text):
    """Extract (deadline_text, location, prize_text) from the card byline."""
    deadline = location = prize = None
    parts = re.split(r"[|]", text)
    for part in parts:
        p = part.strip()
        if not p:
            continue
        if "\U0001f4c5" in p or p.lower().startswith("date"):
            deadline = p.replace("\U0001f4c5", "").strip()
        elif "\U0001f4cd" in p or p.lower().startswith("location"):
            location = p.replace("\U0001f4cd", "").strip()
        elif "\U0001f3c6" in p or p.lower().startswith("prize"):
            prize = p.replace("\U0001f3c6", "").strip()
        else:
            # no marker -> guess by content
            if not deadline and re.search(r"\d{1,2}\s+[a-z]{3}\s+\d{4}", p, re.IGNORECASE):
                deadline = p
            elif not location and any(ch.isalpha() for ch in p) and len(p) < 40:
                location = p
            elif not prize and any(k in p.lower() for k in ("prize", "reward", "cash")):
                prize = p
    return deadline, location, prize


def fetch_internshala():
    """Return a list of internshala listings in the common schema."""
    try:
        html = fetch_html(LISTING_URL)
    except Exception as exc:
        logger.warning(
            "internshala: failed to fetch %s (%s) - likely blocked, skipping",
            LISTING_URL,
            exc,
        )
        return []

    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for card in soup.select("div.box, article"):
        title_el = card.select_one("h2.blog-item-head a")
        if not title_el:
            continue
        url = title_el.get("href", "")
        title = title_el.get_text(" ", strip=True)
        if not title or not url or url in seen:
            continue
        if not _HACK_DETAIL_RE.search(url):
            continue
        seen.add(url)

        byline_el = card.select_one("span.author.vcard, div.meta-author-new")
        deadline, location, prize = _parse_byline(
            byline_el.get_text(" ", strip=True) if byline_el else ""
        )
        if not prize:
            tag = card.select_one("span.prizetag")
            if tag:
                prize = tag.get_text(" ", strip=True)

        listing = build_listing(
            title=title,
            url=url,
            source=SOURCE,
            location=location,
            prize_text=prize,
            deadline_text=deadline,
        )
        if listing:
            out.append(listing)
    return out
