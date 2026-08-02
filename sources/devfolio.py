"""Devfolio hackathon scraper.

Devfolio (devfolio.co/hackathons) is a client-rendered React app. We parse the
embedded __NEXT_DATA__ JSON; if that yields nothing we try a best-effort API
call and finally generic anchor extraction from the HTML.
"""

import json
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html, fetch_json

logger = logging.getLogger(__name__)

SOURCE = "devfolio"
BASE = "https://devfolio.co"
LISTING_URL = f"{BASE}/hackathons"
API_URL = f"{BASE}/api/hackathons"

_DETAIL_RE = re.compile(r"^hackathons/[a-z0-9-]+$", re.IGNORECASE)


def _extract_next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def _walk(node, out):
    if isinstance(node, dict):
        name = node.get("name")
        slug = node.get("slug")
        if (
            isinstance(name, str)
            and isinstance(slug, str)
            and any(k in node for k in ("starts_on", "ends_on", "deadline", "prize", "regions"))
        ):
            out.append(node)
        for value in node.values():
            _walk(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk(value, out)


def _from_candidate(item):
    slug = item.get("slug")
    name = (item.get("name") or "").strip()
    if not name or not slug:
        return None
    url = urljoin(BASE, f"/hackathons/{slug}")
    location = item.get("location") or item.get("region") or item.get("regions")
    if isinstance(location, (list, dict)):
        location = str(location)
    return build_listing(
        title=name,
        url=url,
        source=SOURCE,
        location=location,
        prize_text=item.get("prize") or item.get("prize_pool"),
        deadline_text=item.get("ends_on") or item.get("deadline") or item.get("end_date"),
        tags=[t for t in (item.get("tags") or []) if isinstance(t, str)],
    )


def _fetch_next_data():
    html = fetch_html(LISTING_URL)
    data = _extract_next_data(html)
    if not data:
        return []
    candidates = []
    _walk(data, candidates)
    seen, out = set(), []
    for c in candidates:
        listing = _from_candidate(c)
        if listing and listing["url"] not in seen:
            seen.add(listing["url"])
            out.append(listing)
    return out


def _fetch_api():
    try:
        data = fetch_json(API_URL, params={"status": "open"})
    except Exception as exc:
        logger.warning("devfolio: API attempt failed (%s)", exc)
        return []
    items = data.get("data") or data.get("hackathons") or []
    if isinstance(items, dict):
        items = items.get("data", [])
    return [l for l in (_from_candidate(i) for i in items if isinstance(i, dict)) if l]


def _fetch_cards():
    """Parse the server-rendered hackathon cards on devfolio.co/hackathons."""
    html = fetch_html(LISTING_URL)
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []

    for card in soup.select("[class*='CompactHackathonCard']"):
        link = card.find("a", href=True)
        if not link:
            continue
        title_el = link.find("h3")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        url = link["href"]
        if not title or url in seen:
            continue

        chips = {
            p.get_text(" ", strip=True).lower()
            for p in card.find_all("p")
        }
        if "ended" in chips:
            continue

        if "online" in chips:
            location = "Online"
        elif "offline" in chips:
            location = "Offline"
        else:
            location = None

        start_text = next(
            (
                p.get_text(" ", strip=True).strip()
                for p in card.find_all("p")
                if re.match(r"^starts \d{2}/\d{2}/\d{2}$", p.get_text(" ", strip=True).strip().lower())
            ),
            None,
        )
        deadline = None
        if start_text:
            m = re.search(r"(\d{2})/(\d{2})/(\d{2})", start_text)
            if m:
                day, month, yy = m.groups()
                deadline = f"{2000 + int(yy)}-{month}-{day}"

        seen.add(url)
        listing = build_listing(
            title=title,
            url=url,
            source=SOURCE,
            location=location,
            deadline_text=deadline,
        )
        if listing:
            out.append(listing)
    return out


def _fetch_anchor_fallback():
    html = fetch_html(LISTING_URL)
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if _DETAIL_RE.search(href.strip("/")):
            url = urljoin(BASE, href)
            title = a.get_text(" ", strip=True)
            if title and url not in seen:
                seen.add(url)
                listing = build_listing(title=title, url=url, source=SOURCE)
                if listing:
                    out.append(listing)
    return out


def fetch_devfolio():
    """Return a list of devfolio listings in the common schema."""
    try:
        listings = _fetch_cards()
        if listings:
            logger.info("devfolio: got %d from SSR cards", len(listings))
            return listings
        logger.warning("devfolio: no SSR cards found")
    except Exception as exc:
        logger.warning("devfolio: card parsing failed (%s)", exc)

    try:
        listings = _fetch_next_data()
        if listings:
            logger.info("devfolio: got %d from __NEXT_DATA__", len(listings))
            return listings
        logger.warning("devfolio: __NEXT_DATA__ had no candidates")
    except Exception as exc:
        logger.warning("devfolio: __NEXT_DATA__ parse failed (%s)", exc)

    try:
        listings = _fetch_api()
        if listings:
            logger.info("devfolio: got %d from API", len(listings))
            return listings
    except Exception as exc:
        logger.warning("devfolio: API failed (%s)", exc)

    try:
        return _fetch_anchor_fallback()
    except Exception as exc:
        logger.warning("devfolio: HTML fallback failed (%s)", exc)
        return []
