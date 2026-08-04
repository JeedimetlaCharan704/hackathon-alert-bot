"""Tests for the SQLite layer using a temporary database file."""

from pathlib import Path

import pytest

import university_intel.db as db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    yield db


def _university(name="Test University"):
    return db.University(
        id=None, name=name, state="Telangana", city="Hyderabad", website="https://x.in"
    )


def test_add_and_get_university(tmp_db):
    uid = tmp_db.add_university(_university())
    assert uid is not None
    got = tmp_db.get_university(uid)
    assert got.name == "Test University"
    assert got.state == "Telangana"
    assert got.active is True


def test_add_duplicate_university_ignored(tmp_db):
    tmp_db.add_university(_university())
    second = tmp_db.add_university(_university())
    assert second is None  # INSERT OR IGNORE + lastrowid is stale
    assert len(tmp_db.list_universities()) == 1


def test_remove_university(tmp_db):
    uid = tmp_db.add_university(_university())
    assert tmp_db.remove_university(uid) is True
    assert tmp_db.remove_university(uid) is False


def test_active_filter(tmp_db):
    uid = tmp_db.add_university(_university())
    tmp_db.add_university(_university("Second U"))
    tmp_db.set_university_active(uid, False)
    active = tmp_db.list_universities(active_only=True)
    assert [u.name for u in active] == ["Second U"]


def test_source_lifecycle(tmp_db):
    uid = tmp_db.add_university(_university())
    src = tmp_db.Source(id=None, university_id=uid, source_type="rss", url="https://x.in/feed")
    assert tmp_db.add_source(src) is True
    assert tmp_db.add_source(src) is False  # duplicate
    sources = tmp_db.list_sources(uid)
    assert len(sources) == 1
    assert sources[0].source_type == "rss"
    tmp_db.set_source_enabled(sources[0].id, False)
    assert tmp_db.list_sources(uid, enabled_only=True) == []


def test_event_lifecycle(tmp_db):
    uid = tmp_db.add_university(_university())
    ev = tmp_db.Event(
        id=None,
        university_id=uid,
        title="Hackathon 2026",
        description="desc",
        url="https://x.in/hack",
        date="2026-10-01",
        category="Hackathon",
        source="Test University-rss",
        hash=tmp_db.url_hash("https://x.in/hack"),
    )
    assert tmp_db.add_event(ev) is True
    assert tmp_db.add_event(ev) is False  # same hash
    assert tmp_db.event_exists(url="https://x.in/hack") is True
    assert tmp_db.event_exists(hash_value=ev.hash) is True
    tmp_db.mark_posted(ev.hash)
    s = tmp_db.stats()
    assert s["events"] == 1
    assert s["posted"] == 1


def test_stats_shape(tmp_db):
    s = tmp_db.stats()
    for key in ("universities", "sources", "events", "posted", "last_scan", "by_category"):
        assert key in s


def test_url_hash_stable():
    assert db.url_hash("https://x.in/a") == db.url_hash("https://x.in/a")
    assert db.url_hash("https://x.in/a") != db.url_hash("https://x.in/b")
