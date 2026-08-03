"""Codeforces contest scraper (public API).

Returns upcoming (phase == BEFORE) contests. Codeforces does not publish prize
amounts in this feed, so listings carry prize_value=None (they alert because
codeforces is in LIKELY_CASH_SOURCES).
"""

import logging

from sources.common import build_listing, fetch_json

logger = logging.getLogger(__name__)

SOURCE = "codeforces"
API_URL = "https://codeforces.com/api/contest.list"

TAGS = ["contest", "coding", "competitive programming"]


def _to_listing(contest):
    cid = contest.get("id")
    name = contest.get("name")
    if not cid or not name:
        return None
    url = f"https://codeforces.com/contest/{cid}"
    start = contest.get("startTimeSeconds")
    deadline = None
    if start:
        import datetime

        deadline = datetime.datetime.fromtimestamp(
            int(start), tz=datetime.timezone.utc
        ).strftime("%Y-%m-%d")
    return build_listing(
        title=name,
        url=url,
        source=SOURCE,
        location="Online",
        deadline_text=deadline,
        tags=TAGS,
    )


def fetch_codeforces():
    """Return a list of upcoming Codeforces contest listings."""
    data = fetch_json(API_URL)
    contests = data.get("result") or []
    listings = [
        _to_listing(c) for c in contests if c.get("phase") == "BEFORE"
    ]
    return [l for l in listings if l]
