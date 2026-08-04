"""Tests for the deduplicator (monkeypatched DB layer, no real database)."""

import asyncio

import university_intel.db as db
from university_intel.dedupe import Deduplicator


def _dedupe(monkeypatch, titles=(), known_urls=()):
    known_hashes = {db.url_hash(u) for u in known_urls}
    monkeypatch.setattr(
        "university_intel.dedupe.event_exists",
        lambda url=None, hash_value=None: hash_value in known_hashes if hash_value else False,
    )
    monkeypatch.setattr(
        "university_intel.dedupe.main_bot_db.is_duplicate", lambda url: False
    )
    monkeypatch.setattr("university_intel.dedupe.recent_titles", lambda limit=500: list(titles))
    monkeypatch.setattr("university_intel.dedupe.recent_hashes", lambda limit=2000: set())
    d = Deduplicator()
    return d


def test_url_hash_duplicate(monkeypatch):
    d = _dedupe(monkeypatch, known_urls=["https://x/a"])
    assert asyncio.run(d.is_duplicate(url="https://x/a", title="T", date=None)) == "url_hash"


def test_main_bot_already_sent(monkeypatch):
    d = _dedupe(monkeypatch, titles=["Some title"])
    monkeypatch.setattr(
        "university_intel.dedupe.main_bot_db.is_duplicate", lambda url: True
    )
    reason = asyncio.run(d.is_duplicate(url="https://x/new", title="Other", date=None))
    assert reason == "main_bot_already_sent"


def test_title_exact_duplicate(monkeypatch):
    d = _dedupe(monkeypatch, titles=["Techfest 2026"])
    reason = asyncio.run(
        d.is_duplicate(url="https://x/new", title="Techfest 2026", date=None)
    )
    assert reason == "title_exact"


def test_title_and_date_duplicate(monkeypatch):
    d = _dedupe(monkeypatch, titles=["Techfest 2026"])
    reason = asyncio.run(
        d.is_duplicate(url="https://x/new", title="techfest 2026", date="2026-09-20")
    )
    assert reason == "title_and_date"


def test_title_similar_duplicate(monkeypatch):
    d = _dedupe(monkeypatch, titles=["National Hackathon 2026 registration open"])
    reason = asyncio.run(
        d.is_duplicate(
            url="https://x/new",
            title="National Hackathon 2026 registration open!",
            date=None,
        )
    )
    assert reason == "title_similar"


def test_fresh_event_not_duplicate(monkeypatch):
    d = _dedupe(monkeypatch, titles=["Something else"])
    reason = asyncio.run(
        d.is_duplicate(url="https://x/new", title="Brand New Ideathon", date=None)
    )
    assert reason is None
