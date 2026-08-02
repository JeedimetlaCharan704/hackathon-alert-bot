"""Reskilll hackathon scraper (reskilll.com/allhacks).

The listing is server-rendered. Each card has an `a.allhackname` title link and
registration start/end dates. The page includes many old events - the deadline
filter drops anything already closed.
"""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html

logger = logging.getLogger(__name__)

SOURCE = "reskilll"
BASE = "https://reskilll.com"
LISTING_URL = f"{BASE}/allhacks"

_HACK_DETAIL_RE = re.compile(r"(/hack/|hackathon)", re.IGNORECASE)


def _card_deadline(card):
    rows = card.select("div.hackresgiterdate")
    if not rows:
        return None
    # Last registration date in the card is the deadline.
    for row in reversed(rows):
        text = row.get_text(" ", strip=True)
        if text:
            return text
    return None


def fetch_reskilll():
    """Return a list of reskilll listings in the common schema."""
    try:
        html = fetch_html(LISTING_URL)
    except Exception as exc:
        logger.warning("reskilll: failed to fetch %s (%s)", LISTING_URL, exc)
        return []

    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for card in soup.select("div.hackathonCard, div.allhackcard"):
        link = None
        for a in card.find_all("a", href=True):
            if _HACK_DETAIL_RE.search(a["href"]):
                link = a
                break
        if not link:
            continue
        url = urljoin(BASE, link["href"])
        title = (link.get("title") or link.get_text(" ", strip=True) or "").strip()
        if not title or url in seen:
            continue
        seen.add(url)

        text = card.get_text(" ", strip=True)
        listing = build_listing(
            title=title,
            url=url,
            source=SOURCE,
            prize_text=_sentence(text, ("prize", "cash", "reward")),
            deadline_text=_card_deadline(card) or _sentence(text, ("deadline", "registration end")),
        )
        if listing:
            out.append(listing)
    return out


def _sentence(text, markers):
    for sentence in re.split(r"[.!?\n]+", text):
        if any(m in sentence.lower() for m in markers):
            return sentence.strip()
    return None
