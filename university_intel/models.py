"""Dataclasses for the University Intelligence domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Source types recognised by the adapters / discovery.
SOURCE_TYPES = (
    "rss",
    "events_page",
    "news_page",
    "innovation_page",
    "announcements_page",
    "sitemap",
    "generic_page",
)

# The 15 classification categories.
CATEGORIES = (
    "Hackathon",
    "Coding Contest",
    "Ideathon",
    "Startup Challenge",
    "Innovation Challenge",
    "AI Competition",
    "Research Competition",
    "Workshop",
    "Bootcamp",
    "Internship",
    "Grant",
    "Scholarship",
    "Conference",
    "Tech Fest",
    "Other",
)


@dataclass
class University:
    name: str
    state: str
    website: str
    city: str | None = None
    rss_url: str | None = None
    events_url: str | None = None
    innovation_url: str | None = None
    active: bool = True
    last_scan: datetime | None = None
    id: int | None = None


@dataclass
class Source:
    university_id: int
    source_type: str
    url: str
    enabled: bool = True
    discovered: bool = False
    id: int | None = None


@dataclass
class Event:
    university_id: int
    title: str
    description: str
    url: str
    date: str | None
    category: str
    source: str
    hash: str
    posted: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: int | None = None
