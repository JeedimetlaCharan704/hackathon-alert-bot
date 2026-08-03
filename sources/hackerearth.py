"""HackerEarth event scraper.

Uses the public chrome-extension events JSON endpoint. Returns upcoming
hackathons + coding challenges. Prize amounts are not in this feed, so
listings carry prize_value=None (alerts because hackerearth is in
LIKELY_CASH_SOURCES).
"""

import logging

from sources.common import build_listing, fetch_json

logger = logging.getLogger(__name__)

SOURCE = "hackerearth"
API_URL = "https://www.hackerearth.com/chrome-extension/events/"

TAGS = ["hackathon", "contest", "challenge"]


def _to_listing(event):
    title = event.get("title")
    url = event.get("url")
    if not title or not url:
        return None
    status = (event.get("status") or "").lower()
    if status not in ("upcoming", "ongoing", "running", ""):
        return None
    return build_listing(
        title=title,
        url=url,
        source=SOURCE,
        location="Online",
        deadline_text=event.get("end_utc_tz") or event.get("end_tz"),
        tags=TAGS + [event.get("challenge_type", "")] if event.get("challenge_type") else TAGS,
    )


def fetch_hackerearth():
    """Return a list of HackerEarth event listings."""
    data = fetch_json(API_URL)
    events = data.get("response") or []
    listings = [_to_listing(e) for e in events]
    return [l for l in listings if l]
