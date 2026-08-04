"""Scheduler: runs the scan loop every SCAN_INTERVAL_MINUTES with retries."""

from __future__ import annotations

import asyncio
import logging
import time

from university_intel.config import RETRY_ATTEMPTS, SCAN_INTERVAL_MINUTES
from university_intel.db import init_db
from university_intel.scanner import run_scan

logger = logging.getLogger(__name__)

_CONSECUTIVE_FAILURES = 0


async def run_scheduler() -> None:
    """Run the scan immediately, then every SCAN_INTERVAL_MINUTES forever."""
    global _CONSECUTIVE_FAILURES
    init_db()
    logger.info("Scheduler started (interval=%d minutes)", SCAN_INTERVAL_MINUTES)
    while True:
        started = time.monotonic()
        try:
            report = await run_scan(publish=True)
            _CONSECUTIVE_FAILURES = 0
            logger.info(
                "Scheduled scan done in %.1fs: %s",
                time.monotonic() - started,
                {k: v for k, v in report.items() if k != "stats"},
            )
        except Exception:
            _CONSECUTIVE_FAILURES += 1
            logger.error("Scheduled scan failed", exc_info=True)
            if _CONSECUTIVE_FAILURES >= RETRY_ATTEMPTS:
                logger.warning("Too many consecutive failures; giving this cycle a rest.")
                _CONSECUTIVE_FAILURES = 0
        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)
