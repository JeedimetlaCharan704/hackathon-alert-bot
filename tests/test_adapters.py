"""Tests for the RSS and listing-page adapters using a fake HTTP client."""

from university_intel.adapters.events import EventsPageAdapter
from university_intel.adapters.rss import RssAdapter

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Uni News</title>
    <item>
      <title>National Hackathon 2026 announced</title>
      <link>https://uni.in/events/hackathon-2026</link>
      <description>Register now for the national hackathon.</description>
      <pubDate>Mon, 02 Aug 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Admission Notice 2026-27</title>
      <link>https://uni.in/admissions/notice-2026</link>
      <description>Admissions open.</description>
      <pubDate>Mon, 02 Aug 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

EVENTS_PAGE_HTML = """<html>
<body>
  <h1>Events</h1>
  <a href="/events/coding-contest-2026">Coding Contest 2026</a>
  <a href="/events">All events</a>
  <a href="/about">About us</a>
  <a href="/privacy">Privacy</a>
  <a href="https://facebook.com/uni">Facebook</a>
</body>
</html>"""

DETAIL_HTML = """<html>
<head><title>Coding Contest 2026 - Uni</title>
<meta name="description" content="Test your DSA skills. Prizes for winners."></head>
<body><h1>Coding Contest 2026</h1><p>Conducted on 15 October 2026.</p></body>
</html>"""


class FakeHttp:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    async def fetch(self, url, **kwargs):
        for key, value in sorted(self.pages.items(), key=lambda kv: -len(kv[0])):
            if key in url:
                return value
        raise RuntimeError(f"no fixture for {url}")

    def absolute_url(self, base, href):
        from urllib.parse import urljoin

        return urljoin(base, href) if href.startswith(("http", "/")) else None


def test_rss_adapter():
    http = FakeHttp({"uni.in/feed": RSS_XML})
    adapter = RssAdapter()
    import asyncio

    items = asyncio.run(adapter.scan(http, "https://uni.in/feed"))
    assert len(items) == 2
    assert items[0].title == "National Hackathon 2026 announced"
    assert items[0].url == "https://uni.in/events/hackathon-2026"
    assert items[0].date == "2026-08-02"


def test_events_page_adapter_visits_promising_links():
    http = FakeHttp(
        {
            "uni.in/events": EVENTS_PAGE_HTML,
            "coding-contest-2026": DETAIL_HTML,
        }
    )
    adapter = EventsPageAdapter()
    import asyncio

    items = asyncio.run(adapter.scan(http, "https://uni.in/events"))
    assert any("Coding Contest 2026" in i.title for i in items)
    assert all("facebook" not in i.url for i in items)
