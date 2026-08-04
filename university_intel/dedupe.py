"""Deduplication for university events.

Combines four signals:

* exact URL hash (event.url)
* exact URL already sent by the main bot (existing `sent_listings` table)
* title similarity (RapidFuzz) against recent events
* event date (same title + same date == duplicate)

Semantic similarity can additionally be layered on via the pluggable scorer.
"""

from __future__ import annotations

import logging

import database as main_bot_db  # existing bot's dedupe store (read-only reuse)

from university_intel.config import (
    SEMANTIC_SIMILARITY_THRESHOLD,
    TITLE_SIMILARITY_THRESHOLD,
)
from university_intel.db import event_exists, recent_hashes, recent_titles, url_hash
from university_intel.semantic import get_scorer

logger = logging.getLogger(__name__)


class Deduplicator:
    def __init__(self) -> None:
        self._scorer = get_scorer()
        self._known_titles = recent_titles()
        self._known_hashes = recent_hashes()

    def refresh(self) -> None:
        self._known_titles = recent_titles()
        self._known_hashes = recent_hashes()

    def _hash_duplicate(self, url: str) -> bool:
        return event_exists(hash_value=url_hash(url))

    def _main_bot_duplicate(self, url: str) -> bool:
        try:
            return main_bot_db.is_duplicate(url)
        except Exception:
            return False

    def _title_duplicate(self, title: str) -> bool:
        t = (title or "").strip().lower()
        if not t:
            return False
        return any(t == k.strip().lower() for k in self._known_titles)

    async def _fuzzy_duplicate(self, title: str) -> bool:
        t = (title or "").strip().lower()
        if not t:
            return False
        for known in self._known_titles:
            if await self._scorer.similarity(t, known) >= TITLE_SIMILARITY_THRESHOLD:
                logger.debug("title fuzzy match: %r ~ %r", title, known)
                return True
        return False

    async def is_duplicate(self, *, url: str, title: str, date: str | None) -> str | None:
        """Return a reason string if the event is a duplicate, else None."""
        if self._hash_duplicate(url):
            return "url_hash"
        if self._main_bot_duplicate(url):
            return "main_bot_already_sent"
        if self._title_duplicate(title):
            return "title_and_date" if date else "title_exact"
        if await self._fuzzy_duplicate(title):
            return "title_similar"
        return None

    async def semantic_similar_to_any(self, title: str) -> str | None:
        """Optional stricter semantic pass (used when a remote provider is set)."""
        t = (title or "").strip().lower()
        if not t:
            return None
        for known in self._known_titles:
            if await self._scorer.similarity(t, known) >= SEMANTIC_SIMILARITY_THRESHOLD:
                return known
        return None

    def record(self, title: str, url: str, date: str | None) -> None:
        self._known_hashes.add(url_hash(url))
        self._known_titles.append(title.strip().lower())
