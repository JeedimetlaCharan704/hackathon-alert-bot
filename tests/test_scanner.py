"""Tests for the scan pipeline's normalization/gating logic."""

import asyncio
from unittest.mock import AsyncMock

import university_intel.scanner as scanner
from university_intel.adapters.base import RawItem


def _uni():
    from university_intel.models import University

    return University(name="Test U", state="Telangana", website="https://x.in", id=1)


def test_drops_empty_and_short_titles(monkeypatch):
    monkeypatch.setattr("university_intel.scanner.MIN_TITLE_LENGTH", 8)
    monkeypatch.setattr("university_intel.scanner.PUBLISH_OTHER_CATEGORY", False)
    monkeypatch.setattr("university_intel.scanner.REQUIRE_TITLE_SIGNAL", False)
    assert scanner.normalize_item(RawItem(url="https://x.in/a", title=""), _uni(), "src") is None
    assert scanner.normalize_item(RawItem(url="https://x.in/a", title="hi"), _uni(), "src") is None


def test_drops_other_category_when_disabled(monkeypatch):
    monkeypatch.setattr("university_intel.scanner.PUBLISH_OTHER_CATEGORY", False)
    monkeypatch.setattr("university_intel.scanner.REQUIRE_TITLE_SIGNAL", False)
    item = RawItem(url="https://x.in/a", title="Campus gets a new water tank")
    assert scanner.normalize_item(item, _uni(), "src") is None


def test_keeps_other_category_when_enabled(monkeypatch):
    monkeypatch.setattr("university_intel.scanner.PUBLISH_OTHER_CATEGORY", True)
    monkeypatch.setattr("university_intel.scanner.REQUIRE_TITLE_SIGNAL", False)
    item = RawItem(url="https://x.in/a", title="Campus gets a new water tank")
    ev = scanner.normalize_item(item, _uni(), "src")
    assert ev is not None
    assert ev.category == "Other"


def test_title_signal_gate(monkeypatch):
    monkeypatch.setattr("university_intel.scanner.PUBLISH_OTHER_CATEGORY", True)
    monkeypatch.setattr("university_intel.scanner.REQUIRE_TITLE_SIGNAL", True)
    item = RawItem(url="https://x.in/a", title="Generic news item without keywords")
    assert scanner.normalize_item(item, _uni(), "src") is None
    item2 = RawItem(url="https://x.in/b", title="National Hackathon 2026 begins")
    assert scanner.normalize_item(item2, _uni(), "src") is not None


def test_run_scan_aggregates_reports(monkeypatch):
    async def fake_scan_university(university, http, dedupe, *, publish=True):
        return {"new": 2, "duplicates": 1, "filtered": 5, "published": 1, "failed": 0}

    fake_close = AsyncMock()
    fake_http = AsyncMock()
    fake_http.close = fake_close

    monkeypatch.setattr(scanner, "scan_university", fake_scan_university)
    monkeypatch.setattr(
        scanner, "list_universities", lambda active_only=True: [_uni(), _uni()]
    )

    def make_http():
        return fake_http

    monkeypatch.setattr(scanner, "AsyncHttp", lambda: make_http())
    monkeypatch.setattr(scanner, "stats", lambda: {"dummy": True})

    totals = asyncio.run(scanner.run_scan(publish=True))
    assert totals["universities"] == 2
    assert totals["new"] == 4
    assert totals["duplicates"] == 2
    assert totals["published"] == 2
    assert totals["stats"] == {"dummy": True}
    fake_close.assert_awaited()
