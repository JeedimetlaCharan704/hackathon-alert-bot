"""SQLite persistence for University Intelligence.

Uses the same database file as the existing bot (data/sent_listings.db) so the
existing `sent_listings` dedupe table and these new tables live side by side.
Everything is additive — the existing bot's tables are never touched.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from university_intel.config import DB_PATH
from university_intel.models import Event, Source, University

_SCHEMA = """
CREATE TABLE IF NOT EXISTS universities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    city TEXT,
    website TEXT NOT NULL,
    rss_url TEXT,
    events_url TEXT,
    innovation_url TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    last_scan TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    discovered INTEGER NOT NULL DEFAULT 0,
    UNIQUE (university_id, source_type, url)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL REFERENCES universities(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    date TEXT,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    hash TEXT NOT NULL UNIQUE,
    posted INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_university ON sources(university_id);
CREATE INDEX IF NOT EXISTS idx_events_university ON events(university_id);
CREATE INDEX IF NOT EXISTS idx_events_posted ON events(posted);
CREATE INDEX IF NOT EXISTS idx_events_hash ON events(hash);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _row_to_university(row: sqlite3.Row) -> University:
    return University(
        id=row["id"],
        name=row["name"],
        state=row["state"],
        city=row["city"],
        website=row["website"],
        rss_url=row["rss_url"],
        events_url=row["events_url"],
        innovation_url=row["innovation_url"],
        active=bool(row["active"]),
        last_scan=(
            datetime.fromisoformat(row["last_scan"]) if row["last_scan"] else None
        ),
    )


def _row_to_source(row: sqlite3.Row) -> Source:
    return Source(
        id=row["id"],
        university_id=row["university_id"],
        source_type=row["source_type"],
        url=row["url"],
        enabled=bool(row["enabled"]),
        discovered=bool(row["discovered"]),
    )


# ---------------------------------------------------------------------------
# Universities
# ---------------------------------------------------------------------------


def add_university(u: University) -> int | None:
    """Insert a university. Returns its id, or None if it already existed."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO universities "
            "(name, state, city, website, rss_url, events_url, innovation_url, active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                u.name,
                u.state,
                u.city,
                u.website,
                u.rss_url,
                u.events_url,
                u.innovation_url,
                int(u.active),
            ),
        )
        if cur.rowcount == 0:
            return None
        return cur.lastrowid


def get_university(university_id: int) -> University | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM universities WHERE id = ?", (university_id,)
        ).fetchone()
    return _row_to_university(row) if row else None


def find_university(name: str) -> University | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM universities WHERE lower(name) = lower(?)", (name,)
        ).fetchone()
    return _row_to_university(row) if row else None


def list_universities(active_only: bool = False) -> list[University]:
    sql = "SELECT * FROM universities"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY state, name"
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [_row_to_university(r) for r in rows]


def remove_university(university_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM universities WHERE id = ?", (university_id,))
        return cur.rowcount > 0


def set_university_active(university_id: int, active: bool) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE universities SET active = ? WHERE id = ?",
            (int(active), university_id),
        )


def touch_last_scan(university_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE universities SET last_scan = ? WHERE id = ?",
            (time.strftime("%Y-%m-%d %H:%M:%S"), university_id),
        )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def add_source(s: Source) -> bool:
    """Insert a source. Returns True if newly added, False if it already exists."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO sources "
            "(university_id, source_type, url, enabled, discovered) "
            "VALUES (?, ?, ?, ?, ?)",
            (s.university_id, s.source_type, s.url, int(s.enabled), int(s.discovered)),
        )
        return cur.rowcount > 0


def list_sources(university_id: int, enabled_only: bool = True) -> list[Source]:
    sql = "SELECT * FROM sources WHERE university_id = ?"
    if enabled_only:
        sql += " AND enabled = 1"
    sql += " ORDER BY source_type"
    with _connect() as conn:
        rows = conn.execute(sql, (university_id,)).fetchall()
    return [_row_to_source(r) for r in rows]


def set_source_enabled(source_id: int, enabled: bool) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sources SET enabled = ? WHERE id = ?", (int(enabled), source_id)
        )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def add_event(e: Event) -> bool:
    """Insert a new event. Returns True if inserted, False if hash already exists."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO events "
            "(university_id, title, description, url, date, category, source, hash, "
            " posted, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                e.university_id,
                e.title,
                e.description,
                e.url,
                e.date,
                e.category,
                e.source,
                e.hash,
                int(e.posted),
                e.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        return cur.rowcount > 0


def event_exists(url: str | None = None, hash_value: str | None = None) -> bool:
    with _connect() as conn:
        if hash_value:
            row = conn.execute(
                "SELECT 1 FROM events WHERE hash = ?", (hash_value,)
            ).fetchone()
        elif url:
            row = conn.execute(
                "SELECT 1 FROM events WHERE url = ?", (url,)
            ).fetchone()
        else:
            return False
    return row is not None


def recent_titles(limit: int = 500) -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT title FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [r["title"] for r in rows]


def recent_hashes(limit: int = 2000) -> set[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT hash FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return {r["hash"] for r in rows}


def mark_posted(hash_value: str, posted_at: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE events SET posted = 1 WHERE hash = ?", (hash_value,)
        )
        if posted_at:
            conn.execute(
                "UPDATE events SET created_at = ? WHERE hash = ? AND posted = 1",
                (posted_at, hash_value),
            )


def stats() -> dict:
    with _connect() as conn:
        n_universities = conn.execute(
            "SELECT COUNT(*) FROM universities WHERE active = 1"
        ).fetchone()[0]
        n_sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        n_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        n_posted = conn.execute(
            "SELECT COUNT(*) FROM events WHERE posted = 1"
        ).fetchone()[0]
        last_scan = conn.execute(
            "SELECT MAX(last_scan) FROM universities"
        ).fetchone()[0]
        row = conn.execute(
            "SELECT category, COUNT(*) c FROM events GROUP BY category "
            "ORDER BY c DESC LIMIT 8"
        ).fetchall()
        by_category = {r["category"]: r["c"] for r in row}
    return {
        "universities": n_universities,
        "sources": n_sources,
        "events": n_events,
        "posted": n_posted,
        "last_scan": last_scan,
        "by_category": by_category,
    }


def has_any_university() -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM universities LIMIT 1").fetchone()
    return row is not None
