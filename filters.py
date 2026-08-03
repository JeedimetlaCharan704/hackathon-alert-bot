"""Rule-based filtering and channel routing (no AI/LLM anywhere)."""

import logging
import re
from datetime import datetime, timezone

from config import (
    EXCLUDE_LOCATIONS,
    KEYWORDS,
    LIKELY_CASH_SOURCES,
    MIN_PRIZE_INR,
    MIN_PRIZE_USD,
    PASS_LIKELY_CASH_PRIZE,
    PASS_UNKNOWN_PRIZE,
    REQUIRE_KEYWORD_MATCH,
)

logger = logging.getLogger(__name__)


def _text_matches(text: str, keyword: str) -> bool:
    """Word-boundary match for single words, substring for phrases."""
    text = text.lower()
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def extract_tags(listing: dict) -> list:
    """Synthesize display tags from the configured KEYWORDS list."""
    text = f"{listing.get('title', '')} {' '.join(listing.get('tags') or [])}"
    return [kw for kw in KEYWORDS if _text_matches(text, kw)]


def _prize_passes(listing: dict) -> bool:
    value = listing.get("prize_value")
    if value is None:
        if PASS_UNKNOWN_PRIZE:
            return True
        # No amount shown, but the source normally awards cash prizes.
        return (
            PASS_LIKELY_CASH_PRIZE
            and listing.get("source") in LIKELY_CASH_SOURCES
        )
    if listing.get("prize_currency") == "INR":
        return value >= MIN_PRIZE_INR
    if listing.get("prize_currency") == "USD":
        return value >= MIN_PRIZE_USD
    # A number was parsed but the currency is unknown - let it through.
    return True


def _keyword_matches(listing: dict) -> bool:
    if not REQUIRE_KEYWORD_MATCH:
        return True
    text = f"{listing.get('title', '')} {' '.join(listing.get('tags') or [])}"
    return any(_text_matches(text, kw) for kw in KEYWORDS)


def _deadline_passes(listing: dict) -> bool:
    deadline = listing.get("deadline")
    if not deadline:
        return True
    try:
        dt = datetime.fromisoformat(deadline)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except ValueError:
        logger.warning("Could not parse deadline %r; allowing listing", deadline)
        return True


def _excluded(listing: dict) -> bool:
    if not EXCLUDE_LOCATIONS:
        return False
    haystack = f"{listing.get('location') or ''} {listing.get('country') or ''}".lower()
    return any(x.strip().lower() in haystack for x in EXCLUDE_LOCATIONS)


def filter_listing(listing: dict) -> bool:
    """Return True if a listing passes all configured rules."""
    if _excluded(listing):
        return False
    if not _keyword_matches(listing):
        return False
    if not _prize_passes(listing):
        return False
    if not _deadline_passes(listing):
        return False
    return True


def route_channel(listing: dict) -> str:
    """Route a listing to a channel key: 'telangana', 'india' or 'global'."""
    if listing.get("is_telangana"):
        return "telangana"
    if listing.get("country") == "India":
        return "india"
    return "global"
