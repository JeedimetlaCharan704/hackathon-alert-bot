"""AtCoder contest scraper.

Parses the upcoming contests table on atcoder.jp/contests. Each upcoming row
links to /contests/<slug> with a <time datetime=...> start. AtCoder does not
publish prize amounts in the listing, so prize_value=None (alerts because
atcoder is in LIKELY_CASH_SOURCES).
"""

import logging

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html

logger = logging.getLogger(__name__)

SOURCE = "atcoder"
LIST_URL = "https://atcoder.jp/contests/"

# AtCoder serves a JS/layout page to non-browser UAs.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TAGS = ["contest", "coding", "competitive programming"]


def _to_listing(row):
    link = row.find("a", href=lambda h: h and h.startswith("/contests/"))
    if not link:
        return None
    url = f"https://atcoder.jp{link['href']}"
    title = link.get_text(" ", strip=True)
    time_el = row.find("time")
    deadline = None
    if time_el:
        dt = (time_el.get("datetime") or "").strip() or time_el.get_text(" ", strip=True)
        if dt:
            deadline = dt.split("T")[0] if "T" in dt else dt.split(" ")[0] if " " in dt else dt
    return build_listing(
        title=title,
        url=url,
        source=SOURCE,
        location="Online",
        deadline_text=deadline,
        tags=TAGS,
    )


def fetch_atcoder():
    """Return a list of upcoming AtCoder contest listings."""
    html = fetch_html(LIST_URL, headers=HEADERS)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one('#contest-table-upcoming table, [class*="contest-table-upcoming"] table')
    if not table:
        logger.warning("atcoder: upcoming table not found")
        return []
    listings = [_to_listing(row) for row in table.select("tbody tr")]
    return [l for l in listings if l]
