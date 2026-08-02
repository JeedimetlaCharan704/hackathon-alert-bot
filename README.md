# Hackathon Alert Bot

A $0-cost automated alert system that scrapes hackathon/tech-contest listings
from multiple public sources, filters them with pure rule-based logic (no
AI/LLM), deduplicates them in a SQLite database, and posts formatted alerts to
three separate Telegram channels:

- **Telangana channel** – hackathons in Telangana/Hyderabad
- **India channel** – other India-based hackathons
- **Global channel** – everything else (international / remote / online)

It runs on a schedule via **GitHub Actions** free tier. No paid hosting, no
paid APIs, no LLM calls.

---

## Features

- Scrapes 7 sources: Devfolio, Unstop, Reskilll, Internshala, Devpost, lablab.ai, MLH
- Rule-based filtering: prize threshold, keyword match, deadline not passed, location exclusions
- SQLite deduplication (`data/sent_listings.db`) committed back to the repo each run so state persists
- One broken source never crashes the run (logged and skipped)
- `--dry-run` flag to test scraper changes without spamming channels
- Respectful scraping: custom User-Agent + short delay between requests

## Project structure

```
hackathon-alert-bot/
├── .github/workflows/run_bot.yml   # scheduled GitHub Action (every 4h + manual)
├── sources/
│   ├── __init__.py
│   ├── common.py                   # shared HTTP, prize/date/location parsing
│   ├── devfolio.py
│   ├── unstop.py
│   ├── reskilll.py
│   ├── internshala.py
│   ├── devpost.py
│   ├── lablab.py
│   └── mlh.py
├── data/sent_listings.db           # created on first run, committed after
├── config.py                       # thresholds, keywords, channel IDs (from env)
├── filters.py                      # filter_listing(), route_channel()
├── telegram_sender.py              # format_message(), send_message()
├── database.py                     # init_db(), is_duplicate(), mark_sent()
├── main.py                         # fetch -> filter -> dedupe -> send
├── requirements.txt
├── .env.example
└── README.md
```

---

## 1. Local setup

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Create your environment file:

```bash
cp .env.example .env
```

Fill in `BOT_TOKEN` and the three channel IDs (see below for how to get them).

### Test locally (no messages sent)

```bash
python main.py --dry-run
```

This fetches every source, filters, and logs what would be sent **without
sending anything**. Use it to check scraper changes.

### Send for real

```bash
python main.py
```

---

## 2. Create the bot and channels (one-time, manual)

### Create the bot with @BotFather

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, follow the prompts, and pick a name + username ending in `bot`.
3. BotFather gives you a token like `123456789:AA...`. Put it in `.env` as `BOT_TOKEN`.

### Create your three channels

1. Telegram → New Channel → name them e.g. `Hackathons Telangana`,
   `Hackathons India`, `Hackathons Global`.
2. Add your bot as an **administrator** of each channel
   (Channel Settings → Administrators → Add Admin → search your bot username).
   Admin rights are required for the bot to post.

### Get each channel's numeric chat ID

1. Post any message in each channel (e.g. "test").
2. Call the Telegram API from a browser/curl with your token:

   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```

3. In the JSON, find your channel under `result[].channel_post.chat` and read
   the `id` field. Public channels/supergroups have negative IDs starting with
   `-100...` (e.g. `-1001234567890`).
4. Put each ID in `.env`:
   - `TELANGANA_CHANNEL_ID`, `INDIA_CHANNEL_ID`, `GLOBAL_CHANNEL_ID`

> Tip: if `getUpdates` returns empty, send another test message in the channel
> first, and make sure the bot is admin.

---

## 3. Run automatically with GitHub Actions

1. Push this repo to GitHub (public repos get unlimited free Actions minutes;
   private repos are still free within the monthly quota — the 4-hourly cron
   keeps runs short and well within it).
2. Add the secrets under **Repo → Settings → Secrets and variables → Actions → New repository secret**:
   | Secret | Value |
   |---|---|
   | `BOT_TOKEN` | your @BotFather token |
   | `TELANGANA_CHANNEL_ID` | Telangana channel chat ID |
   | `INDIA_CHANNEL_ID` | India channel chat ID |
   | `GLOBAL_CHANNEL_ID` | Global channel chat ID |
3. Go to **Actions → Run Hackathon Alert Bot → Run workflow** to trigger a
   manual run and confirm it works.
4. The workflow also runs automatically every 4 hours. After each run it
   commits `data/sent_listings.db` back to the repo so already-sent listings
   are never re-alerted.

---

## 4. Tuning the filters

Everything lives at the top of `config.py`:

- `MIN_PRIZE_INR` / `MIN_PRIZE_USD` – prize thresholds (default 10000 INR / 100 USD)
- `PASS_UNKNOWN_PRIZE` – allow listings with no detectable prize through (default `True`; set `False` to require a qualifying prize)
- `KEYWORDS` – at least one must appear in the title/tags (word-boundary match for single words)
- `EXCLUDE_LOCATIONS` – drop listings whose location/country contains any of these
- `REQUEST_DELAY_SECONDS` – politeness delay between HTTP requests

A listing passes if **all** rules hold: not excluded, keyword matches, prize
meets the threshold (or unknown & `PASS_UNKNOWN_PRIZE`), and deadline is
missing or in the future.

---

## 5. How sources are parsed & known limitations

- **Devpost** – uses its JSON API (`devpost.com/api/hackathons`), which returns
  titles, locations, prize amounts and submission dates.
- **MLH** – MLH retired the old `mlh.io/seasons/*/events.json` feed. The bot
  now parses the schema.org microdata on the current season page
  (`mlh.io/events`, which redirects to the active season). MLH doesn't publish
  prize amounts, so its listings have `prize_value=None` (they still alert
  while `PASS_UNKNOWN_PRIZE=True`).
- **Devfolio** – parses the server-rendered hackathon cards on
  `devfolio.co/hackathons` (title, mode, status, start date).
- **lablab.ai** – extracts the JSON-LD `ItemList` from the page's Next.js RSC
  payload (all events are online → routed to the Global channel).
- **Unstop** – uses the public search endpoint
  (`/api/public/opportunity/search-result`) which returns title, URL, city/
  state/country, end date and a prize paragraph.
- **Reskilll** – parses `reskilll.com/allhacks` cards (title + registration
  dates; the page contains many old events, which the deadline filter drops).
- **Internshala** – parses `internshala.com/competitions/hackathons` cards
  (title, 📅 date, 📍 location, 🏆 prize tag). Internshala frequently blocks
  bots (HTTP 403 / bot-detection page) — when that happens it logs a warning
  and returns nothing; the run continues. If you see 0 internshala listings,
  that's the block, not a bug.

Source scrapers are isolated functions with try/except wrappers. Selectors may
need occasional tweaks when a site changes its markup — run `main.py --dry-run`
after any change to check output before enabling real sends.

---

## 6. Logging & run summary

Uses Python's `logging` module. Each run ends with a summary:

```
Run summary: {'fetched': 42, 'passed_filter': 15, 'sent': {'telangana': 2, 'india': 5, 'global': 8}, 'skipped_duplicates': 3}
```

---

## Notes on constraints

- Zero paid APIs/services.
- No LLM/AI calls — pure rule-based filtering.
- Respects sources: descriptive User-Agent, short delay between requests.
