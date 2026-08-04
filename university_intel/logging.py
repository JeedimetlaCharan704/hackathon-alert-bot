"""Logging for the University Intelligence module.

Writes to `data/university_logs/bot.log` (rotating) and the console. Logs new
events, duplicates, errors, last-scan times and per-scan processing times.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "university_logs"

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger("university_intel")
    root.setLevel(logging.INFO)
    root.propagate = False

    file_handler = RotatingFileHandler(
        LOG_DIR / "bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    root.addHandler(file_handler)
    root.addHandler(console)
    _CONFIGURED = True


def log_scan(university_name: str, elapsed: float, new: int, dupes: int) -> None:
    logger = logging.getLogger("university_intel.scan")
    logger.info(
        "scan %s finished in %.2fs | new=%d duplicates=%d",
        university_name,
        elapsed,
        new,
        dupes,
    )
