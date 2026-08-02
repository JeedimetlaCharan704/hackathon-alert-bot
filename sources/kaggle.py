"""Kaggle competition scraper.

Uses the official Kaggle API (v1/competitions/list) with a free personal API
token (set as KAGGLE_API_TOKEN). Kaggle publishes real prize amounts, so these
listings carry proper prize_value/prize_currency.

Only competitions with a cash prize (USD/INR) are kept - reward-only contests
("Knowledge", "Swag", "Jobs") are dropped.
"""

import logging

from config import MAX_PAGES_PER_SOURCE
from sources.common import build_listing, fetch_json, normalize_prize

logger = logging.getLogger(__name__)

SOURCE = "kaggle"
API_URL = "https://www.kaggle.com/api/v1/competitions/list"

# Non-cash rewards that appear in the "reward" field.
_CASH_CURRENCIES = {"USD", "INR"}


def _api_headers():
    from config import KAGGLE_API_TOKEN

    if not KAGGLE_API_TOKEN:
        logger.warning("KAGGLE_API_TOKEN is not set; kaggle source skipped")
        return None
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Authorization": f"Bearer {KAGGLE_API_TOKEN}",
    }


def _to_listing(comp):
    title = comp.get("title")
    url = comp.get("url")
    if not title or not url:
        return None

    reward = comp.get("reward")
    prize_value, prize_currency = normalize_prize(reward)
    # Keep only cash-prize competitions.
    if prize_currency not in _CASH_CURRENCIES:
        return None

    tags = [
        t.get("nameNullable")
        for t in (comp.get("tags") or [])
        if isinstance(t, dict) and t.get("nameNullable")
    ]

    # Always include "competition" so the keyword gate lets these through
    # (they are already curated to be cash-prize competitions).
    if "competition" not in tags:
        tags = tags + ["competition"]

    return build_listing(
        title=title,
        url=url,
        source=SOURCE,
        location="Online",
        prize_text=reward,
        deadline_text=comp.get("deadline"),
        tags=tags,
    )


def fetch_kaggle():
    """Return a list of Kaggle competition listings in the common schema."""
    headers = _api_headers()
    if not headers:
        return []

    listings = []
    for page in range(1, MAX_PAGES_PER_SOURCE + 1):
        data = fetch_json(API_URL, params={"page": page}, headers=headers)
        items = data if isinstance(data, list) else data.get("competitions") or []
        if not items:
            break
        listings.extend(_to_listing(c) for c in items)
    return [l for l in listings if l]
