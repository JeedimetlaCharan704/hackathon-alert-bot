"""SQLite-backed deduplication store.

The database file lives in `data/sent_listings.db` and is committed back to
the repo after every GitHub Actions run so state persists between runs.
"""

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "sent_listings.db"

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sent_listings (
    url TEXT PRIMARY KEY,
    sent_at TIMESTAMP,
    channel TEXT
)
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


def init_db() -> None:
    """Ensure the sent_listings table exists."""
    with _connect() as conn:
        conn.execute(_TABLE_SQL)


def is_duplicate(url: str) -> bool:
    """Return True if this url has already been sent."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM sent_listings WHERE url = ?", (url,)
        ).fetchone()
    return row is not None


def mark_sent(url: str, channel: str) -> None:
    """Record that a listing was sent to a channel (no-op if already there)."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sent_listings (url, sent_at, channel) "
            "VALUES (?, ?, ?)",
            (url, time.strftime("%Y-%m-%d %H:%M:%S"), channel),
        )
