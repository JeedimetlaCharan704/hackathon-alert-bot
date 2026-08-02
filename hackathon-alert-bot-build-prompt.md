# Build Prompt: Free Hackathon/Tech-Contest Alert Bot

Copy everything below into your AI coding agent (Claude Code, OpenCode, Cursor, etc.) to build the project end-to-end.

---

## PROMPT START

You are building a $0-cost automated alert system that scrapes hackathon/tech-contest listings and sends filtered, deduplicated alerts to three separate Telegram channels (Telangana, India, Global). It runs on a schedule via GitHub Actions — no paid hosting, no paid APIs, no AI/LLM calls required.

### Project goal
Build a Python project that:
1. Scrapes/fetches hackathon and tech-contest listings from multiple public sources
2. Normalizes each listing into a common structure (title, location, country, prize_value, prize_currency, deadline, url, tags, source)
3. Filters listings using rule-based logic (prize threshold, keywords, deadline not passed, location match)
4. Routes each passing listing to the correct Telegram channel based on location:
   - Telangana/Hyderabad-specific → Telangana channel
   - Other India-based → India channel
   - Everything else (global/remote/international) → Global channel
5. Tracks already-sent listings in a local SQLite database to avoid duplicate alerts
6. Sends formatted messages via the Telegram Bot API
7. Runs automatically on a schedule using GitHub Actions (free tier), committing the updated SQLite db back to the repo after each run so state persists between runs

### Tech stack (all free, no paid tiers)
- Python 3.11+
- `requests` + `beautifulsoup4` for scraping (or `feedparser` if a source has RSS)
- `sqlite3` (standard library) for the dedupe database
- Telegram Bot API via `requests` (no need for `python-telegram-bot` library, keep it lightweight — just POST to `https://api.telegram.org/bot<TOKEN>/sendMessage`)
- GitHub Actions for scheduling (cron) and running the script
- No LLM/AI API calls anywhere in this version — pure rule-based filtering

### Data sources to implement scrapers/fetchers for
Start with these (skip any that block scraping or require login; note which ones you skipped and why):
- Devfolio (devfolio.co/hackathons)
- Unstop (unstop.com/hackathons)
- Reskilll (reskilll.com/allhacks)
- Internshala Competitions (internshala.com/competitions/hackathons)
- Devpost (devpost.com/hackathons) — has a documented-ish JSON endpoint, check for `/api/hackathons` style responses first before falling back to HTML scraping
- lablab.ai (lablab.ai/ai-hackathons)
- MLH (mlh.io/seasons/2026/events)

For each source, write an isolated function `fetch_<source>() -> list[dict]` that returns listings in the common schema below. Wrap each in try/except so one broken source doesn't crash the whole run — log the error and continue.

### Common listing schema
```python
{
    "title": str,
    "url": str,                     # unique identifier for dedupe
    "source": str,                  # e.g. "devfolio", "unstop"
    "location": str,                # e.g. "Hyderabad", "Online", "San Francisco"
    "country": str,                 # e.g. "India", "USA", "Global"
    "is_telangana": bool,           # True if location mentions Telangana/Hyderabad
    "prize_value": float | None,    # normalized to a comparable number
    "prize_currency": str | None,   # "INR" or "USD"
    "deadline": str | None,         # ISO date if available
    "tags": list[str],              # e.g. ["AI", "Blockchain"]
    "raw_prize_text": str | None,   # original text, for display in the message
}
```

### Filtering rules (config-driven, put these in a `config.py` or `.env`, not hardcoded)
A listing passes the filter if ALL of the following are true:
- `prize_value >= MIN_PRIZE_INR` (default 10000) OR `prize_value >= MIN_PRIZE_USD` (default 100), matching currency
- At least one tag/keyword from `KEYWORDS` list matches the title or tags (default: `["ai", "blockchain", "web3", "hackathon", "ml", "machine learning", "cybersecurity", "cloud", "robotics", "genai", "llm"]`)
- `deadline` is either `None` (unknown, allow it through) or in the future
- Location is not explicitly excluded (make an `EXCLUDE_LOCATIONS` list, empty by default)

Make thresholds and keyword lists easy to edit at the top of the config file — I will want to tune these after the first week of alerts.

### Routing logic
```python
def route_channel(listing):
    if listing["is_telangana"]:
        return "TELANGANA_CHANNEL_ID"
    elif listing["country"] == "India":
        return "INDIA_CHANNEL_ID"
    else:
        return "GLOBAL_CHANNEL_ID"
```

### Telegram message format
Format each alert like this (use Markdown formatting supported by Telegram's `parse_mode: MarkdownV2` or `HTML` — pick one and escape correctly):

```
🚀 NEW HACKATHON

📍 Location: {location}
🏆 Prize: {raw_prize_text}
🎯 Tags: {tags joined by ", "}
📅 Deadline: {deadline or "Not specified"}
🔗 Apply: {url}
📰 Source: {source}
```

### Deduplication
- SQLite table `sent_listings(url TEXT PRIMARY KEY, sent_at TIMESTAMP, channel TEXT)`
- Before sending, check if `url` already exists — skip if yes
- After successful send, insert the row
- The `.db` file must live in the repo (e.g. `data/sent_listings.db`) and be committed back after each GitHub Actions run so state isn't lost between runs

### Project structure
```
hackathon-alert-bot/
├── .github/
│   └── workflows/
│       └── run_bot.yml          # scheduled GitHub Action
├── sources/
│   ├── __init__.py
│   ├── devfolio.py
│   ├── unstop.py
│   ├── reskilll.py
│   ├── internshala.py
│   ├── devpost.py
│   ├── lablab.py
│   └── mlh.py
├── data/
│   └── sent_listings.db          # created on first run, committed after
├── config.py                     # thresholds, keywords, channel IDs (channel IDs from env)
├── filters.py                    # filter_listing(), route_channel()
├── telegram_sender.py            # send_message(chat_id, text)
├── database.py                   # init_db(), is_duplicate(), mark_sent()
├── main.py                       # orchestrates: fetch all -> filter -> dedupe -> send
├── requirements.txt
├── .env.example                  # BOT_TOKEN, TELANGANA_CHANNEL_ID, INDIA_CHANNEL_ID, GLOBAL_CHANNEL_ID
└── README.md                     # setup instructions, how to get a bot token, how to add channel IDs as GitHub secrets
```

### GitHub Actions workflow requirements
- Trigger: `schedule` cron every 4 hours, plus `workflow_dispatch` for manual runs
- Steps: checkout repo → setup Python → install requirements → run `main.py` (reading secrets from GitHub repo secrets: `BOT_TOKEN`, `TELANGANA_CHANNEL_ID`, `INDIA_CHANNEL_ID`, `GLOBAL_CHANNEL_ID`) → commit and push the updated `data/sent_listings.db` back to the repo if it changed
- Use `actions/checkout@v4`, `actions/setup-python@v5`, and a simple `git add/commit/push` step guarded by a check for changes

### Secrets handling
- Never hardcode the bot token or channel IDs
- Read everything from environment variables, documented in `.env.example`
- README must explain: how to create a bot via @BotFather, how to get a channel's chat ID, and how to add these as GitHub repo secrets (Settings → Secrets and variables → Actions)

### Error handling & logging
- Use Python's `logging` module, not print statements
- Each source fetch failure should log a warning and continue, not crash the run
- Log a summary at the end of each run: total fetched, total passed filter, total sent (broken down by channel), total skipped as duplicates

### What to build first (order of implementation)
1. `database.py` + `config.py` + `filters.py` (core logic, no network calls, easy to unit test)
2. `telegram_sender.py` — test by manually sending one hardcoded message to confirm bot/channel setup works
3. One source scraper (start with Devpost since it may have a JSON-ish endpoint) end-to-end through `main.py`
4. Add remaining source scrapers one at a time
5. GitHub Actions workflow last, once `main.py` runs cleanly end-to-end locally

### Testing instructions to include in README
- How to run locally with a `.env` file before pushing to GitHub
- How to do a dry run (fetch + filter but skip sending) using a `--dry-run` flag on `main.py`, for testing scraper changes without spamming the Telegram channels

### Constraints — do not violate these
- Zero paid APIs or services anywhere in this project
- No LLM/AI calls in this version (rule-based filtering only)
- Must run entirely within GitHub Actions' free tier (public repo = unlimited free minutes; private repo = stay well within the free minutes quota by keeping runs short and 4-hourly, not more frequent)
- Respect each source's robots.txt and avoid hammering servers — add a short delay between requests within each scraper, and set a descriptive User-Agent header

## PROMPT END

---

### After the agent builds it, you still need to do manually (can't be automated by the agent):
1. Message @BotFather on Telegram, create the bot, save the token
2. Create your 3 Telegram channels, add the bot as admin to each
3. Get each channel's numeric chat ID (the agent's README should explain the method — usually via the `getUpdates` API call after posting once manually)
4. Add all 4 secrets (`BOT_TOKEN` + 3 channel IDs) to your GitHub repo under Settings → Secrets and variables → Actions
5. Push the repo, trigger the workflow manually once to confirm it works, then let the cron schedule take over
