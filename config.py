"""Central configuration.

Thresholds, keywords, and location exclusions live at the top of this file so
they are easy to tune. Secrets (bot token + channel IDs) are read from
environment variables only - never hardcode them here.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Telegram secrets (from environment / .env / GitHub secrets)
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Free personal Kaggle API token (https://www.kaggle.com -> Settings -> API).
# Used by sources/kaggle.py to fetch cash-prize competitions.
KAGGLE_API_TOKEN = os.getenv("KAGGLE_API_TOKEN", "").strip()

TELANGANA_CHANNEL_ID = os.getenv("TELANGANA_CHANNEL_ID", "").strip()
INDIA_CHANNEL_ID = os.getenv("INDIA_CHANNEL_ID", "").strip()
GLOBAL_CHANNEL_ID = os.getenv("GLOBAL_CHANNEL_ID", "").strip()

CHANNEL_IDS = {
    "telangana": TELANGANA_CHANNEL_ID,
    "india": INDIA_CHANNEL_ID,
    "global": GLOBAL_CHANNEL_ID,
}

# ---------------------------------------------------------------------------
# Filtering rules - tune these after the first week of alerts
# ---------------------------------------------------------------------------

# Minimum prize that a listing must have to be alerted (per currency).
MIN_PRIZE_INR = 10000
MIN_PRIZE_USD = 100

# If a listing has no detectable prize text, allow it through anyway?
# Default True so sources that do not publish prize amounts still produce
# alerts. Set to False to require a qualifying prize for every alert.
PASS_UNKNOWN_PRIZE = True

# A listing passes if at least one of these appears in its title or tags
# (matched on word boundaries; multi-word phrases match as substrings).
KEYWORDS = [
    "ai",
    "blockchain",
    "web3",
    "hackathon",
    "ml",
    "machine learning",
    "cybersecurity",
    "cloud",
    "robotics",
    "genai",
    "llm",
    # coding contests / challenges (CodeChef, HackerRank, ...)
    "coding",
    "contest",
    "challenge",
    "competitive",
    "programming",
    "algorithm",
    "dsa",
    "codechef",
    "hackerrank",
    "starters",
    "competition",
]

# Any listing whose location or country contains one of these strings is
# dropped. Empty by default.
EXCLUDE_LOCATIONS = []

# ---------------------------------------------------------------------------
# Scraping behaviour
# ---------------------------------------------------------------------------
USER_AGENT = (
    "HackathonAlertBot/1.0 (free hobby project; sends Telegram alerts; "
    "contact the repo owner to opt out)"
)

# Delay between HTTP requests to be polite to source servers.
REQUEST_DELAY_SECONDS = 1.5

# Max pages to crawl per paginated source.
MAX_PAGES_PER_SOURCE = 3
