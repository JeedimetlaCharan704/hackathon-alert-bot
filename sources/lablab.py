"""lablab.ai hackathon scraper.

lablab.ai/ai-hackathons is a Next.js App Router page. The hackathon list is
serialized into the page's RSC payload (`self.__next_f.push(...)`) as a
JSON-LD ItemList. We extract those push chunks, decode the JSON escapes and
read the ItemList entries (title + URL). lablab events are online, so location
is "Online".
"""

import json
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html

logger = logging.getLogger(__name__)

SOURCE = "lablab"
BASE = "https://lablab.ai"
LISTING_URL = f"{BASE}/ai-hackathons"

_EVENT_RE = re.compile(r"^event/[a-z0-9-]+$", re.IGNORECASE)
_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.DOTALL)
_ITEM_RE = re.compile(
    r'\{"@type":"ListItem","position":\d+,"name":"(.*?)","url":"(.*?)"\}',
    re.DOTALL,
)


def _decode(s):
    """Decode a JSON string literal (handles \" and \\uXXXX escapes)."""
    try:
        return json.loads('"' + s + '"')
    except ValueError:
        return s


def _extract_items():
    html = fetch_html(LISTING_URL)
    blob = "".join(_PUSH_RE.findall(html))
    if not blob:
        return []
    blob = blob.replace('\\"', '"')
    items = []
    seen = set()
    for name, url in _ITEM_RE.findall(blob):
        name = _decode(name).strip()
        url = _decode(url)
        if not name or url in seen:
            continue
        seen.add(url)
        items.append((name, url))
    return items


def _fetch_rsc():
    items = _extract_items()
    listings = []
    for name, url in items:
        listing = build_listing(
            title=name,
            url=url,
            source=SOURCE,
            location="Online",
        )
        if listing:
            listings.append(listing)
    return listings


def _fetch_anchor_fallback():
    html = fetch_html(LISTING_URL)
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not _EVENT_RE.search(href.strip("/")):
            continue
        url = urljoin(BASE, href)
        title = a.get_text(" ", strip=True)
        if title and url not in seen:
            seen.add(url)
            listing = build_listing(title=title, url=url, source=SOURCE, location="Online")
            if listing:
                out.append(listing)
    return out


def fetch_lablab():
    """Return a list of lablab listings in the common schema."""
    try:
        listings = _fetch_rsc()
        if listings:
            logger.info("lablab: got %d from RSC ItemList", len(listings))
            return listings
        logger.warning("lablab: no events found in RSC payload")
    except Exception as exc:
        logger.warning("lablab: RSC parse failed (%s)", exc)

    try:
        return _fetch_anchor_fallback()
    except Exception as exc:
        logger.warning("lablab: HTML fallback failed (%s)", exc)
        return []
