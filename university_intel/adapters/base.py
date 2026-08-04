"""Adapter base class + shared extraction helpers.

Every source type implements a small `SourceAdapter` with an async `scan`
method that turns one public URL into a list of RawItems (title/url/snippet/
date). Adapters are registered in the `ADAPTERS` registry and picked by
`source_type`, so adding a new source type is just adding another class.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from university_intel.config import MAX_LINKS_PER_PAGE, MAX_RSS_ENTRIES
from university_intel.http import AsyncHttp

logger = logging.getLogger(__name__)

_SKIP_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".jpg", ".jpeg",
    ".png", ".gif", ".zip", ".tar", ".gz", ".mp4", ".mp3", ".rar", ".7z", ".csv",
)
_SKIP_URL_FRAGMENTS = (
    "login", "signin", "signup", "register", "password", "privacy", "terms",
    "copyright", "about", "contact", "javascript:", "mailto:", "#", "facebook",
    "twitter", "youtube", "instagram", "linkedin", "wa.me", "webmail", "careers",
    "admission", "faq", "help", "site-map", "archives", "search",
)


def normalize_title(text: str) -> str:
    return " ".join((text or "").split())


@dataclass
class RawItem:
    """A raw candidate event pulled from a public university source."""

    url: str
    title: str
    description: str = ""
    date: str | None = None
    extra: dict = field(default_factory=dict)


class SourceAdapter(ABC):
    source_type: str = ""

    @abstractmethod
    async def scan(self, http: AsyncHttp, source_url: str) -> list[RawItem]:
        ...


def is_candidate_link(base: str, url: str, *, allow_keywords: bool = True) -> bool:
    """True if `url` looks like a useful public page worth visiting."""
    lowered = (url or "").lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    if urlparse(lowered).path.lower().endswith(_SKIP_EXTENSIONS):
        return False
    if any(frag in lowered for frag in _SKIP_URL_FRAGMENTS):
        return False
    if allow_keywords and _LINK_KEYWORD_RE.search(urlparse(lowered).path):
        return False  # index/nav pages don't usually need re-walking
    return True


# Navigation-ish path segments we avoid following link-by-link.
_LINK_KEYWORD_RE = re.compile(
    r"/(home|index|about|gallery|faculty|staff|student|alumni|library|sports|"
    r"placement|training|academic|results|fee|admission|hostel|department|"
    r"administration|notices?/|calendar)/",
    re.IGNORECASE,
)


def _extract_meta(soup: BeautifulSoup) -> tuple[str, str]:
    """Return (title, description) from the HTML head."""
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"]
    description = ""
    for attrs in (
        {"name": "description"},
        {"property": "og:description"},
        {"name": "og:description"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            description = tag["content"]
            break
    return normalize_title(title), normalize_title(description)


def _extract_dates(soup: BeautifulSoup) -> list[str]:
    """Best-effort ISO dates found on the page (reuses the bot's date parser)."""
    from sources.common import parse_deadline  # shared helper, no side effects

    text = soup.get_text(" ", strip=True)[:20000]
    # Meta published time is the most reliable signal.
    for attrs in ({"property": "article:published_time"}, {"name": "date"},
                  {"itemprop": "datePublished"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            parsed = parse_deadline(tag["content"])
            if parsed:
                return [parsed]
    parsed = parse_deadline(text)
    return [parsed] if parsed else []


def collect_page_links(http: AsyncHttp, base: str, html: str) -> list[str]:
    """Extract distinct, same-host, non-trivial links from a page's HTML."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        url = http.absolute_url(base, href)
        if not url or url in seen:
            continue
        if not is_candidate_link(base, url):
            continue
        seen.add(url)
        out.append(url)
    return out
