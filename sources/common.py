"""Shared HTTP + normalization helpers for all source scrapers."""

import logging
import re
import time
from datetime import datetime

import requests

from config import REQUEST_DELAY_SECONDS, USER_AGENT

logger = logging.getLogger(__name__)

_session = None

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _http_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    return _session


def fetch_html(url: str, **kwargs) -> str:
    """GET a URL, respecting the polite delay. Raises on failure."""
    time.sleep(REQUEST_DELAY_SECONDS)
    resp = _http_session().get(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.text


def fetch_json(url: str, **kwargs) -> dict:
    """GET a URL as JSON, respecting the polite delay. Raises on failure."""
    time.sleep(REQUEST_DELAY_SECONDS)
    resp = _http_session().get(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Prize parsing -> (value, currency)
# ---------------------------------------------------------------------------

_INR_MARKERS = ("inr", "rupee", "rupees", "rs.", "rs ", "₹", "\u20b9", "lakh", "crore")
_USD_MARKERS = ("usd", "us$", "$")

_SUFFIXES = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "crore": 10_000_000,
    "lakh": 100_000,
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
    "l": 100_000,
}

_NUMBER_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(thousand|million|billion|crore|lakh|k|m|b|l)?",
    re.IGNORECASE,
)


def normalize_prize(raw_text):
    """Turn prize text like '$100,000' or '₹1 Lakh - ₹5 Lakh' into (value, currency).

    Returns (float | None, "INR" | "USD" | None). The largest number found is
    used (best-effort approximation of the top prize / prize pool).
    """
    if not raw_text:
        return None, None
    text = str(raw_text)

    lowered = text.lower()
    if any(m in lowered for m in _INR_MARKERS):
        currency = "INR"
    elif any(m in lowered for m in _USD_MARKERS):
        currency = "USD"
    else:
        currency = None

    # Strip thousands separators (handles both "1,000,000" and "1,00,000"),
    # then match numbers with an optional multiplier suffix.
    clean = re.sub(r",", "", text)
    values = []
    for m in _NUMBER_RE.finditer(clean):
        if not m.group(1):
            continue
        num = float(m.group(1))
        suffix = (m.group(2) or "").lower()
        values.append(num * _SUFFIXES.get(suffix, 1))

    if not values:
        return None, currency
    return max(values), currency


# ---------------------------------------------------------------------------
# Date parsing -> "YYYY-MM-DD" (ISO) or None
# ---------------------------------------------------------------------------

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_MONTH_NAME = (
    r"\bjanuary\b|\bfebruary\b|\bmarch\b|\bapril\b|\bmay\b|\bjune\b|"
    r"\bjuly\b|\baugust\b|\bseptember\b|\boctober\b|\bnovember\b|\bdecember\b|"
    r"\bjan\b|\bfeb\b|\bmar\b|\bapr\b|\bmay\b|\bjun\b|\bjul\b|\baug\b|\bsep\b|"
    r"\boct\b|\bnov\b|\bdec\b"
)
_MONTH_DAY_YEAR = re.compile(
    rf"({_MONTH_NAME})\s+(\d{{1,2}})\w*,?\s+(\d{{4}})",
    re.IGNORECASE,
)
_MONTH_RANGE_YEAR = re.compile(
    rf"({_MONTH_NAME})\s+(\d{{1,2}})\w*\s*[-]\s*(\d{{1,2}})\w*,?\s+(\d{{4}})",
    re.IGNORECASE,
)
_DAY_MONTH_YEAR = re.compile(
    rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_NAME})\s*,?\s+(\d{{4}})",
    re.IGNORECASE,
)
_YEAR_MONTH = re.compile(
    r"(\d{4})-(\d{1,2})",
)
_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def _candidate_dates(text: str):
    text = " " + text + " "
    found = []

    # Prefer explicit ISO dates when present. Without this, the year-month
    # fallback below ("2026-08" -> Aug 28) would override a real ISO deadline
    # like "2026-08-05" and wrongly push it to the 28th.
    iso_found = []
    for m in _ISO.finditer(text):
        try:
            iso_found.append(datetime(int(m[1]), int(m[2]), int(m[3])).date())
        except ValueError:
            pass
    if iso_found:
        return iso_found

    for m in _MONTH_RANGE_YEAR.finditer(text):
        # e.g. "Dec 11 - 15, 2026" -> use the later day as the deadline
        try:
            month = _MONTHS[m.group(1).lower()]
            found.append(datetime(int(m.group(4)), month, int(m.group(3))).date())
        except ValueError:
            pass

    for m in _MONTH_DAY_YEAR.finditer(text):
        try:
            month = _MONTHS[m.group(1).lower()]
            found.append(datetime(int(m.group(3)), month, int(m.group(2))).date())
        except ValueError:
            pass

    for m in _DAY_MONTH_YEAR.finditer(text):
        try:
            month = _MONTHS[m.group(2).lower()]
            found.append(datetime(int(m.group(3)), month, int(m.group(1))).date())
        except ValueError:
            pass

    for m in _YEAR_MONTH.finditer(text):
        try:
            found.append(datetime(int(m.group(1)), int(m.group(2)), 28).date())
        except ValueError:
            pass

    return found


def parse_deadline(text):
    """Best-effort parse of a deadline string into 'YYYY-MM-DD'.

    When a date range is present (e.g. 'May 5 - May 7'), the latest date is
    returned (the submission deadline). Returns None if nothing parses.
    """
    if not text:
        return None
    dates = _candidate_dates(text)
    if not dates:
        return None
    return max(dates).isoformat()


# ---------------------------------------------------------------------------
# Location normalization -> country, is_telangana
# ---------------------------------------------------------------------------

_TELANGANA_KEYWORDS = ("telangana", "hyderabad")

_INDIA_KEYWORDS = (
    "india",
    # major metros
    "hyderabad", "bengaluru", "bangalore", "chennai", "mumbai", "pune",
    "delhi", "noida", "gurgaon", "gurugram", "kolkata", "ahmedabad",
    "jaipur", "indore", "nagpur", "lucknow", "kochi", "cochin",
    "trivandrum", "thiruvananthapuram", "coimbatore", "bhopal", "surat",
    "goa", "chandigarh", "bhubaneswar", "guwahati", "patna", "varanasi",
    "visakhapatnam", "vizag", "vijayawada", "mysore", "mysuru", "kanpur",
    "agra", "amritsar", "jodhpur", "udaipur", "jaipur", "dehradun",
    "raipur", "ranchi", "jammu", "srinagar", "shillong", "imphal",
    "agartala", "aizawl", "kohima", "itanagar", "gangtok", "pondicherry",
    "panaji", "silchar", "dharamshala", "bharat",
    # states / union territories
    "telangana", "andhra pradesh", "andhra", "karnataka", "tamil nadu",
    "tamilnadu", "kerala", "maharashtra", "karnataka", "gujarat", "rajasthan",
    "punjab", "haryana", "uttar pradesh", "uttarakhand", "west bengal",
    "madhya pradesh", "odisha", "orissa", "bihar", "assam", "jharkhand",
    "chhattisgarh", "goa", "himachal pradesh", "himachal", "jammu and kashmir",
    "jammu", "kashmir", "manipur", "meghalaya", "mizoram", "nagaland",
    "tripura", "sikkim", "arunachal pradesh", "ladakh", "delhi ncr", "ncr",
)

_GLOBAL_LOCATION_MARKERS = ("online", "remote", "virtual", "global", "anywhere")


def detect_country(location, country_hint=None):
    """Return 'India', 'Telangana' is handled separately, or 'Global'."""
    if country_hint:
        return country_hint
    loc = (location or "").lower().strip()
    if not loc or any(m in loc for m in _GLOBAL_LOCATION_MARKERS):
        return "Global"
    if "india" in loc:
        return "India"
    for kw in _INDIA_KEYWORDS:
        if kw in loc:
            return "India"
    return "Global"


def detect_telangana(location, country=None) -> bool:
    haystack = f"{location or ''} {country or ''}".lower()
    return any(k in haystack for k in _TELANGANA_KEYWORDS)


# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------


def build_listing(
    *,
    title,
    url,
    source,
    location=None,
    country=None,
    prize_text=None,
    deadline_text=None,
    tags=None,
):
    """Build a dict in the common listing schema."""
    title = (title or "").strip()
    if not title or not url:
        return None

    country = detect_country(location, country)
    prize_value, prize_currency = normalize_prize(prize_text)

    return {
        "title": title,
        "url": url,
        "source": source,
        "location": _truncate(location or "", 80),
        "country": country,
        "is_telangana": detect_telangana(location, country),
        "prize_value": prize_value,
        "prize_currency": prize_currency,
        "deadline": parse_deadline(deadline_text),
        "tags": tags or [],
        "raw_prize_text": _truncate(prize_text, 160),
    }


def _truncate(text, limit):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
