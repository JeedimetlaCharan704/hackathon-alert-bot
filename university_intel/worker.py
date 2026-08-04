"""Entry points for University Intelligence.

Modes:
    python -m university_intel.worker --once [--dry-run]   # one scan, exit (GitHub Actions)
    python -m university_intel.worker                       # daemon: scheduler (+ commands)
    python -m university_intel.worker --seed                # (re)load the seed university list
    python -m university_intel.worker --forcescan           # full scan with forced discovery
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from university_intel import logging as module_logging
from university_intel.db import has_any_university, init_db, stats
from university_intel.scheduler import run_scheduler
from university_intel.scanner import run_scan
from university_intel.seeds import seed_universities

module_logging.setup_logging()
logger = logging.getLogger(__name__)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="University Intelligence worker")
    parser.add_argument("--once", action="store_true", help="Run a single scan then exit")
    parser.add_argument("--dry-run", action="store_true", help="Scan but do not publish")
    parser.add_argument("--seed", action="store_true", help="Load the seed university list")
    parser.add_argument("--forcescan", action="store_true", help="Scan with forced discovery")
    args = parser.parse_args()

    init_db()

    if args.seed:
        added = seed_universities()
        logger.info("Seeded %d university(s).", added)
        return

    if not has_any_university():
        added = seed_universities()
        logger.info("Auto-seeded %d university(s) (empty database).", added)

    if args.once:
        report = await run_scan(publish=not args.dry_run, force_discovery=args.forcescan)
        logger.info("Once-scan summary: %s", {k: v for k, v in report.items() if k != "stats"})
        return

    from university_intel.admin import run_command_listener

    await asyncio.gather(run_scheduler(), run_command_listener())


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
