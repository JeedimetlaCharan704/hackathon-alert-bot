"""The scan pipeline: one university -> raw items -> events -> publish.

Pure orchestration; each stage lives in its own module so the pieces stay
pluggable. The pipeline is:

  adapters scan sources -> normalize RawItems -> classify + ignore-filter ->
  dedupe (url hash / title / date / main-bot store) -> store events ->
  publish via the existing Telegram pipeline
"""

from __future__ import annotations

import logging
import time

from university_intel.adapters import ADAPTERS, RawItem
from university_intel.classifier import PRIZE_CATEGORIES, mentions_prize, process, title_has_signal
from university_intel.config import (
    MIN_TITLE_LENGTH,
    PUBLISH_OTHER_CATEGORY,
    REQUIRE_TITLE_SIGNAL,
    UNIVERSITY_REQUIRE_PRIZE,
)
from university_intel.db import (
    add_event,
    init_db,
    list_sources,
    list_universities,
    stats,
    touch_last_scan,
    url_hash,
)
from university_intel.dedupe import Deduplicator
from university_intel.discovery import discover_and_store
from university_intel.http import AsyncHttp
from university_intel.models import Event, University
from university_intel.publisher import publish_event

logger = logging.getLogger(__name__)


def normalize_item(item: RawItem, university: University, source_label: str) -> Event | None:
    """Run classification + ignore filter. Returns None if it shouldn't publish."""
    title = (item.title or "").strip()
    if len(title) < MIN_TITLE_LENGTH:
        logger.debug("too short [%s] %r", university.name, title)
        return None
    if REQUIRE_TITLE_SIGNAL and not title_has_signal(title):
        logger.debug("no title signal [%s] %s", university.name, title)
        return None
    category = process(title, item.description)
    if category is None:
        logger.debug("filtered out [%s] %s", university.name, title)
        return None
    if category == "Other" and not PUBLISH_OTHER_CATEGORY:
        logger.debug("not an opportunity [%s] %s", university.name, title)
        return None
    if UNIVERSITY_REQUIRE_PRIZE and category not in PRIZE_CATEGORIES:
        if not mentions_prize(title, item.description):
            logger.debug("no prize mention [%s] %s", university.name, title)
            return None
    return Event(
        id=None,
        university_id=university.id,
        title=title,
        description=item.description,
        url=item.url,
        date=item.date,
        category=category,
        source=source_label,
        hash=url_hash(item.url),
        posted=False,
    )


async def scan_university(
    university: University,
    http: AsyncHttp,
    dedupe: Deduplicator,
    *,
    publish: bool = True,
) -> dict:
    """Scan one university and return a small report dict."""
    started = time.monotonic()
    report = {"new": 0, "duplicates": 0, "filtered": 0, "published": 0, "failed": 0}

    sources = list_sources(university.id)
    if not sources:
        # Nothing registered yet — try automatic discovery from the homepage.
        await discover_and_store(university, http)
        sources = list_sources(university.id)
        if not sources:
            logger.info("%s: no sources found after discovery", university.name)

    for source in sources:
        adapter = ADAPTERS.get(source.source_type)
        if adapter is None:
            logger.warning("no adapter for source_type %r", source.source_type)
            continue
        try:
            items = await adapter.scan(http, source.url)
        except Exception:
            logger.warning(
                "%s: adapter %s failed for %s",
                university.name,
                source.source_type,
                source.url,
                exc_info=True,
            )
            continue

        for item in items:
            event = normalize_item(item, university, f"{university.name}-{source.source_type}")
            if event is None:
                report["filtered"] += 1
                continue

            reason = await dedupe.is_duplicate(
                url=event.url, title=event.title, date=event.date
            )
            if reason:
                report["duplicates"] += 1
                logger.info("duplicate [%s] %s (%s)", university.name, event.title, reason)
                continue

            # Only persist an event once it has actually been posted, so a
            # dry-run never burns an event for later real publishing.
            if publish:
                if await publish_event(event, university):
                    event.posted = True
                    add_event(event)
                    report["published"] += 1
                    logger.info("new [%s] %s (%s)", university.name, event.title, event.category)
                else:
                    report["failed"] += 1
            else:
                report["new"] += 1
                logger.info("(dry-run) would publish: %s", event.title)

            dedupe.record(event.title, event.url, event.date)

    touch_last_scan(university.id)
    from university_intel.logging import log_scan

    log_scan(university.name, time.monotonic() - started, report["new"], report["duplicates"])
    return report


async def run_scan(*, publish: bool = True, force_discovery: bool = False) -> dict:
    """Scan every active university. Returns aggregate stats."""
    init_db()
    totals = {"universities": 0, "new": 0, "duplicates": 0, "filtered": 0, "published": 0, "failed": 0}
    http = AsyncHttp()
    await http.start()
    dedupe = Deduplicator()
    try:
        universities = list_universities(active_only=True)
        totals["universities"] = len(universities)
        for university in universities:
            if force_discovery:
                try:
                    await discover_and_store(university, http)
                except Exception:
                    logger.warning("forced discovery failed for %s", university.name, exc_info=True)
            try:
                report = await scan_university(university, http, dedupe, publish=publish)
            except Exception:
                logger.error("scan crashed for %s", university.name, exc_info=True)
                continue
            for key in ("new", "duplicates", "filtered", "published", "failed"):
                totals[key] += report[key]
    finally:
        await http.close()
    totals["stats"] = stats()
    return totals
