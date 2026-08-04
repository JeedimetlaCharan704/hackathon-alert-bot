"""Configuration for the University Intelligence module.

Reads from the same .env as the rest of the bot (loaded by the root config.py
too, but we load it ourselves so the module is self-contained).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Telegram (shared with the existing bot — never create a second token)
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_CHAT_IDS", "").split(",")
    if x.strip()
]

# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL", "30"))
COMMAND_POLL_SECONDS = int(os.getenv("COMMAND_POLL_SECONDS", "5"))

# ---------------------------------------------------------------------------
# Database (same SQLite file the existing bot commits back to GitHub)
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL and not DATABASE_URL.startswith("sqlite"):
    raise ValueError(
        "DATABASE_URL: University Intelligence currently supports SQLite. "
        "Remove DATABASE_URL or point it at a .db / sqlite:// path."
    )
DB_PATH = Path(os.getenv("DB_PATH", "")).resolve() if os.getenv("DB_PATH") else (
    Path(__file__).resolve().parents[1] / "data" / "sent_listings.db"
)

# ---------------------------------------------------------------------------
# Scanning behaviour
# ---------------------------------------------------------------------------
USER_AGENT = (
    "UniversityIntelBot/0.1 (free hobby project; reads only public pages; "
    "contact the repo owner to opt out)"
)
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "1.2"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_LINKS_PER_PAGE = int(os.getenv("MAX_LINKS_PER_PAGE", "200"))
MAX_RSS_ENTRIES = int(os.getenv("MAX_RSS_ENTRIES", "30"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("RETRY_BACKOFF_SECONDS", "5"))
SCAN_ALLOWED_HOSTS = os.getenv("SCAN_ALLOWED_HOSTS", "").strip()

# ---------------------------------------------------------------------------
# Deduplication / classification
# ---------------------------------------------------------------------------
TITLE_SIMILARITY_THRESHOLD = float(os.getenv("TITLE_SIMILARITY_THRESHOLD", "0.88"))
SEMANTIC_SIMILARITY_THRESHOLD = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.92"))

# Publish announcements that don't match any opportunity category? Defaults to
# False so generic university news doesn't spam the channel.
PUBLISH_OTHER_CATEGORY = (
    os.getenv("PUBLISH_OTHER_CATEGORY", "false").strip().lower() in {"1", "true", "yes"}
)
# Require the title itself to signal an opportunity (keeps generic news out
# even when the description mentions keywords).
REQUIRE_TITLE_SIGNAL = (
    os.getenv("REQUIRE_TITLE_SIGNAL", "true").strip().lower() in {"1", "true", "yes"}
)
MIN_TITLE_LENGTH = int(os.getenv("MIN_TITLE_LENGTH", "8"))

# Semantic scorer. "local" = free offline fuzzy (default). "grok" = optional
# remote embeddings using GROK_API_KEY (requires a paid xAI account).
SEMANTIC_PROVIDER = os.getenv("SEMANTIC_PROVIDER", "local").strip().lower()
GROK_API_KEY = os.getenv("GROK_API_KEY", "").strip()

# Auto-seed the university list on first run if the table is empty.
SEED_ON_EMPTY = os.getenv("SEED_ON_EMPTY", "true").strip().lower() in {"1", "true", "yes"}

# Discovered source URLs are persisted so re-scans reuse them.
ENABLE_DISCOVERY = os.getenv("ENABLE_DISCOVERY", "true").strip().lower() in {"1", "true", "yes"}
