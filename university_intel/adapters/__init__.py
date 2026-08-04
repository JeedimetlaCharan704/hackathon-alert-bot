"""Source adapter registry. Plug-and-play: add a class, register it here.

Note: the sitemap adapter is deliberately NOT registered for scanning — it is
used only by the discovery tool to find event pages. Sitemaps contain hundreds
of index pages, not publishable announcements.
"""

from university_intel.adapters.base import RawItem, SourceAdapter
from university_intel.adapters.events import (
    AnnouncementsPageAdapter,
    EventsPageAdapter,
    GenericPageAdapter,
    InnovationPageAdapter,
    NewsPageAdapter,
)
from university_intel.adapters.rss import RssAdapter

ADAPTERS: dict[str, SourceAdapter] = {
    adapter.source_type: adapter()
    for adapter in (
        RssAdapter,
        EventsPageAdapter,
        InnovationPageAdapter,
        NewsPageAdapter,
        AnnouncementsPageAdapter,
        GenericPageAdapter,
    )
}

__all__ = [
    "ADAPTERS",
    "RawItem",
    "SourceAdapter",
]
