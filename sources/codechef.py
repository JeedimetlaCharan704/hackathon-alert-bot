"""CodeChef contest scraper.

Uses the public listing API (same one the website uses). Returns future +
currently running contests. CodeChef does not publish prize amounts in this
feed, so listings carry prize_value=None (they alert while PASS_UNKNOWN_PRIZE
is on).
"""

import logging

from sources.common import build_listing, fetch_json

logger = logging.getLogger(__name__)

SOURCE = "codechef"
API_URL = "https://www.codechef.com/api/list/contests/all"

# The site serves this endpoint only to browser-ish clients.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.codechef.com/contests",
}

TAGS = ["contest", "coding", "competitive programming"]


def _to_listing(contest):
    code = contest.get("contest_code")
    title = contest.get("contest_name")
    if not code or not title:
        return None
    url = f"https://www.codechef.com/{code}"
    return build_listing(
        title=title,
        url=url,
        source=SOURCE,
        location="Online",
        deadline_text=contest.get("contest_end_date_iso"),
        tags=TAGS,
    )


def fetch_codechef():
    """Return a list of CodeChef contest listings in the common schema."""
    data = fetch_json(
        API_URL,
        params={
            "sort_by": "END",
            "sorting_order": "asc",
            "offset": 0,
            "mode": "all",
        },
        headers=HEADERS,
    )
    contests = (data.get("future_contests") or []) + (
        data.get("present_contests") or []
    )
    listings = [_to_listing(c) for c in contests if c.get("contest_code")]
    return [l for l in listings if l]
