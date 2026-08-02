"""HackerRank contest scraper.

Uses the public REST feed (same one the website uses). Returns upcoming/active
contests. HackerRank does not publish prize amounts in this feed, so listings
carry prize_value=None (they alert while PASS_UNKNOWN_PRIZE is on).
"""

import logging

from sources.common import build_listing, fetch_json

logger = logging.getLogger(__name__)

SOURCE = "hackerrank"
API_URL = "https://www.hackerrank.com/rest/contests/upcoming"

# The site serves this endpoint only to browser-ish clients.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

TAGS = ["contest", "coding", "competitive programming"]


def _to_listing(model):
    slug = model.get("slug")
    title = model.get("name")
    if not slug or not title:
        return None
    url = f"https://www.hackerrank.com/contests/{slug}"
    return build_listing(
        title=title,
        url=url,
        source=SOURCE,
        location="Online",
        deadline_text=model.get("get_endtimeiso"),
        tags=TAGS,
    )


def fetch_hackerrank():
    """Return a list of HackerRank contest listings in the common schema."""
    data = fetch_json(API_URL, headers=HEADERS)
    models = data.get("models") or []
    listings = [_to_listing(m) for m in models if m.get("slug")]
    return [l for l in listings if l]
