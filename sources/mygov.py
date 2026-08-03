"""MyGov / Innovate India challenge scraper.

Parses the Innovate India portal homepage for challenge links, then visits each
challenge page to grab its title and submission deadline. Language/locale
variants and nav pages are filtered out. Low volume, but these are official
government challenges/grants students can apply to.
"""

import logging
import re

from bs4 import BeautifulSoup

from sources.common import build_listing, fetch_html

logger = logging.getLogger(__name__)

SOURCE = "mygov"
HOME_URL = "https://innovateindia.mygov.in/"

_SKIP = {
    "as", "bn", "gu", "hi", "kn", "ml", "mr", "ta", "te", "pa", "or", "ur",
    "login-with-otp", "ministry", "about", "all-past-initiatives",
}

_SLUG = re.compile(r"^https://innovateindia\.mygov\.in/([a-z0-9-]+)/?$")


def _challenge_slugs(soup):
    slugs = set()
    for a in soup.find_all("a", href=True):
        m = _SLUG.match(a["href"].strip())
        if m and m.group(1) not in _SKIP:
            slugs.add(m.group(1))
    return slugs


def _scrape_challenge(slug):
    url = f"https://innovateindia.mygov.in/{slug}/"
    try:
        html = fetch_html(url)
    except Exception as exc:
        logger.warning("mygov: %s failed (%s)", slug, exc)
        return None
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.find("h1") or soup.find("h2")
    title = title_el.get_text(" ", strip=True) if title_el else slug.replace("-", " ").title()

    body_text = " ".join(
        soup.get_text(" ", strip=True).split()
    )[:3000]
    listing = build_listing(
        title=title,
        url=url,
        source=SOURCE,
        location="India",
        deadline_text=body_text,
        tags=["hackathon", "competition", "government"],
    )
    return listing


def fetch_mygov():
    """Return a list of Innovate India challenge listings."""
    html = fetch_html(HOME_URL)
    soup = BeautifulSoup(html, "html.parser")
    slugs = _challenge_slugs(soup)
    listings = [_scrape_challenge(s) for s in sorted(slugs)]
    return [l for l in listings if l]
