# 🚀 Hackathon Alert Bot

A **$0-cost, fully automated** hackathon alert system that scrapes hackathon and
tech-contest listings from multiple public sources, filters them with pure
rule-based logic (**no AI/LLM calls**), deduplicates them in a SQLite database,
and posts formatted alerts to **three separate Telegram channels**:

| Channel | Content |
|---|---|
| **Telangana** | Hackathons in Telangana / Hyderabad |
| **India** | Other India-based hackathons |
| **Global** | Everything else (international / remote / online) |

It runs on a schedule via **GitHub Actions** (free tier), so **it works 24/7
even when your laptop is off**. No paid hosting, no paid APIs, no LLM calls.

---

## How it works (the big picture)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            GITHUB ACTIONS (free cloud)                     │
│                                                                            │
│   Every 4 hours the cron fires ────────────────────────────────┐           │
│                                                                ▼           │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────────┐   │
│   │  Fetch       │ → │  Filter      │ → │  Route + Dedupe + Send        │   │
│   │  (7 sources) │   │  (rules)     │   │  (SQLite + Telegram API)      │   │
│   └──────┬───────┘   └──────┬───────┘   └──────────────┬───────────────┘   │
│          │                 │                           │                   │
│          ▼                 ▼                           ▼                   │
│   ~350 raw listings    ~50 pass rules             posted to Telegram         │
│   (typical run)       (prize + keyword +         channels (only NEW ones,  │
│                        deadline not passed)       duplicates skipped)      │
│                                                                            │
│   After the run, the updated data/sent_listings.db is committed back to    │
│   the repo so the next run knows what was already sent.                    │
└────────────────────────────────────────────────────────────────────────────┘
```

**In one sentence:** every 4 hours, GitHub's servers fetch hackathon listings →
keep only the ones that match your rules → check the SQLite "already sent" log →
post the new ones to the right Telegram channel → save the log back to GitHub.

Because the state is committed back to the repo, the bot remembers what it
already alerted across every future run, even though each run starts fresh.

---

## Features

- **9 sources scraped:** Devfolio, Unstop, Reskilll, Internshala, Devpost,
  lablab.ai, MLH, CodeChef, HackerRank — hackathons **and** coding contests
  (CodeChef Starters, HackerRank contests, etc.)
- **Rule-based filtering:** prize threshold, keyword match, deadline not passed,
  location exclusions — configurable in `config.py`
- **SQLite deduplication:** `data/sent_listings.db` stores every sent URL and is
  committed back to the repo after each run so nothing is ever alerted twice
- **Fault tolerant:** one broken source is logged and skipped — it never crashes
  the run
- **`--dry-run` mode:** test scraper/filter changes locally without spamming
  your channels
- **Respectful scraping:** custom User-Agent + short delay between requests
- **Free forever:** GitHub Actions free tier, no paid APIs or services

---

## Project structure

```
hackathon-alert-bot/
├── .github/
│   └── workflows/
│       └── run_bot.yml        # scheduled GitHub Action (every 4h + manual)
├── sources/
│   ├── __init__.py            # ALL_SOURCES registry
│   ├── common.py              # shared HTTP, prize/date/location parsing
│   ├── devfolio.py            # devfolio.co/hackathons
│   ├── unstop.py              # unstop.com/hackathons
│   ├── reskilll.py            # reskilll.com/allhacks
│   ├── internshala.py         # internshala.com/competitions/hackathons
│   ├── devpost.py             # devpost.com/hackathons
│   ├── lablab.py              # lablab.ai/ai-hackathons
│   ├── mlh.py                 # mlh.io/events
│   ├── codechef.py            # codechef.com contests (public API)
│   └── hackerrank.py          # hackerrank.com contests (public API)
├── data/
│   └── sent_listings.db       # dedupe database (committed after each run)
├── config.py                  # thresholds, keywords, channel IDs (from env)
├── filters.py                 # filter_listing(), route_channel()
├── telegram_sender.py         # format_message(), send_message()
├── database.py                # init_db(), is_duplicate(), mark_sent()
├── main.py                    # orchestrator: fetch → filter → dedupe → send
├── requirements.txt
├── .env.example               # template for local testing
└── README.md
```

### How the pieces fit together

| File | Role |
|---|---|
| `main.py` | The orchestrator. Runs every source, filters everything, routes to channels, sends. Also prints a run summary. |
| `sources/*.py` | Each source is an isolated `fetch_<source>() -> list[dict]` wrapped in try/except. A failure logs a warning and moves on. |
| `config.py` | All tunable knobs: prize thresholds, keywords, exclusions, delays. Secrets (bot token + channel IDs) come from **environment variables only** — never hardcoded. |
| `filters.py` | Pure rule logic: does a listing pass the prize/keyword/deadline rules, and which channel does it belong to? |
| `telegram_sender.py` | Renders a listing as an HTML-formatted Telegram message and POSTs it via the raw Bot API. |
| `database.py` | SQLite store that remembers every URL already sent so nothing is duplicated. |
| `.github/workflows/run_bot.yml` | The free cloud scheduler that runs `main.py` every 4 hours and commits the database back. |

---

## The data flow, step by step

1. **Fetch** — `main.py` calls every `fetch_<source>()` one after another (with a
   short politeness delay between calls). Each scraper returns listings in a
   common schema:

   ```python
   {
       "title": str,
       "url": str,                # unique identifier for dedupe
       "source": str,             # e.g. "devfolio", "unstop"
       "location": str,           # e.g. "Hyderabad", "Online", "San Francisco"
       "country": str,            # e.g. "India", "USA", "Global"
       "is_telangana": bool,      # True if Telangana/Hyderabad
       "prize_value": float|None, # normalized for comparison
       "prize_currency": str|None,# "INR" or "USD"
       "deadline": str|None,      # ISO date
       "tags": list[str],
       "raw_prize_text": str|None # original text, for the alert message
   }
   ```

2. **Filter** — every listing must pass **all** these rules (`filters.py`):
   - Prize is `>= MIN_PRIZE_INR` (INR) or `>= MIN_PRIZE_USD` (USD) — or prize is
     unknown and `PASS_UNKNOWN_PRIZE` is `True`
   - At least one `KEYWORDS` entry appears in the title/tags
   - Deadline is missing or in the future
   - Location is not in `EXCLUDE_LOCATIONS`

3. **Route** — each passing listing is sent to one channel:
   - Telangana/Hyderabad → **Telangana** channel
   - Country == India → **India** channel
   - Everything else → **Global** channel

4. **Dedupe** — before sending, `is_duplicate(url)` is checked. Already sent →
   skipped. Never sent → posted and then `mark_sent(url, channel)` records it.

5. **Send** — the listing is rendered as a Telegram message (HTML parse mode)
   and POSTed to `https://api.telegram.org/bot<TOKEN>/sendMessage`.

6. **Persist** — after the run, GitHub Actions commits `data/sent_listings.db`
   back to the repo so the next run starts with the full history.

### Example alert message

```
🚀 NEW HACKATHON

📍 Location: Hyderabad, Telangana
🏆 Prize: ₹2,00,000
🎯 Tags: ai, hackathon
📅 Deadline: 2026-09-30

🔗 Apply: Open listing
📰 Source: devfolio
```

---

## Local setup

Requires **Python 3.11+**.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then fill in your real values
```

### Test locally (nothing gets sent)

```bash
python main.py --dry-run
```

This fetches every source, filters, and logs **what would be sent** — without
sending anything. Use this after any scraper/filter change.

### Send for real (from your machine)

```bash
python main.py
```

---

## One-time Telegram setup (manual, ~5 minutes)

This is the only part that can't be automated (it requires your Telegram account).

### 1. Create the bot with @BotFather

1. Open Telegram → message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`, follow the prompts, choose a name + username ending in `bot`
3. Copy the token (format: `123456789:AA...`) → put it in `.env` as `BOT_TOKEN`

### 2. Create your 3 channels

1. Telegram → New Channel → name them e.g. `Hackathons Telangana`,
   `Hackathons India`, `Hackathons Global`
2. Add your bot as an **administrator** of each channel:
   Channel Settings → Administrators → Add Admin → search your bot's **username**
   (e.g. `hackathonsalertbot`). Admin rights are required for posting.
   - If the bot doesn't appear in search: open the bot and press **Start** first,
     then retry — or add it as a **Member** first, then promote it to Admin.

### 3. Get each channel's chat ID

Post any message in each channel, then open this URL in your browser:

```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

Look under `result[].channel_post.chat.id` — public channels have negative IDs
starting with `-100...` (e.g. `-1001234567890`). Put them in `.env` as
`TELANGANA_CHANNEL_ID`, `INDIA_CHANNEL_ID`, `GLOBAL_CHANNEL_ID`.

---

## Deploying to GitHub (free 24/7 scheduling)

### 1. Push the repo

```bash
git init
git add .
git commit -m "Initial commit: hackathon alert bot"
git branch -M main
git remote add origin https://github.com/<your-username>/hackathon-alert-bot.git
git push -u origin main
```

### 2. Add the 4 secrets

Under **Repo → Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `BOT_TOKEN` | your @BotFather token |
| `TELANGANA_CHANNEL_ID` | Telangana channel chat ID |
| `INDIA_CHANNEL_ID` | India channel chat ID |
| `GLOBAL_CHANNEL_ID` | Global channel chat ID |

### 3. Trigger a manual run to confirm

Go to **Actions → Run Hackathon Alert Bot → Run workflow**. Watch it go green,
then check your channels for alerts.

### 4. Let the schedule take over

The workflow is already configured to run **every 4 hours**:

```yaml
schedule:
  - cron: "0 */4 * * *"   # 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC
```

It runs on GitHub's servers — **your laptop can be off**. After every run it
commits `data/sent_listings.db` back, so already-sent listings are never re-alerted.

> ⚠️ Note: the cron times are **UTC**. For India (IST = UTC+5:30) that's
> 5:30 AM, 9:30 AM, 1:30 PM, 5:30 PM, 9:30 PM, 1:30 AM.

---

## Tuning the filters

Everything lives at the top of `config.py`:

| Setting | Default | Meaning |
|---|---|---|
| `MIN_PRIZE_INR` | `10000` | Minimum prize for INR listings |
| `MIN_PRIZE_USD` | `100` | Minimum prize for USD listings |
| `PASS_UNKNOWN_PRIZE` | `True` | Allow listings with no detectable prize (sources like MLH don't publish prizes) |
| `KEYWORDS` | `["ai", "blockchain", ...]` | At least one must match the title/tags |
| `EXCLUDE_LOCATIONS` | `[]` | Drop listings whose location matches |
| `REQUEST_DELAY_SECONDS` | `1.5` | Politeness delay between HTTP requests |
| `MAX_PAGES_PER_SOURCE` | `3` | Max pages crawled per paginated source |

---

## Sources & known limitations

- **Devpost** — uses its JSON API (`devpost.com/api/hackathons`).
- **MLH** — parses schema.org microdata on the season page. MLH doesn't publish
  prize amounts, so these have `prize_value=None` (they still alert while
  `PASS_UNKNOWN_PRIZE=True`).
- **Devfolio** — parses server-rendered hackathon cards.
- **lablab.ai** — extracts the JSON-LD `ItemList` from the page's Next.js payload
  (all events are online → Global channel).
- **Unstop** — uses the public search endpoint (`/api/public/opportunity/search-result`).
- **Reskilll** — parses `reskilll.com/allhacks` cards (contains many old events,
  which the deadline filter drops).
- **CodeChef** — uses the public contest API (`/api/list/contests/all`), returns
  future + running contests (Starters, rated contests). No prize amounts in the
  feed, so these alert as "Prize: Not specified".
- **HackerRank** — uses the public REST feed (`/rest/contests/upcoming`). Old
  archived contests still appear in that feed, but the deadline filter drops
  them. No prize amounts either.
- **Internshala** — parses competition cards. Internshala **frequently blocks bots**
  (HTTP 403). When blocked it logs a warning and returns nothing — the run
  continues. Seeing 0 Internshala listings is the block, not a bug.

Selectors may need occasional tweaks when a site changes its markup. Run
`python main.py --dry-run` after any change to check output before enabling real
sends.

---

## Logging & run summary

Each run logs a final summary, e.g.:

```
Run summary: {'fetched': 334, 'passed_filter': 46, 'sent': {'global': 23}, 'skipped_duplicates': 23}
```

You can see the full logs of every run on GitHub under **Actions → Run Hackathon
Alert Bot → (pick a run)**.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot won't post to a channel | Make sure the bot is **admin** of the channel, then re-trigger a run. |
| Bot not found in "Add Admin" search | Press **Start** on the bot first, or add as Member then promote. |
| No alerts at all | Check the Action logs for a `Run summary` and the channel IDs in Secrets are correct (must start with `-100...`). |
| 0 Internshala listings | It's bot-blocked — that's expected, other sources still work. |
| Push from Actions fails ("Permission denied") | The workflow needs `permissions: contents: write` (already included in this repo). |

---

## Constraints honored

- **$0** — no paid hosting, no paid APIs.
- **No AI/LLM** — pure rule-based filtering.
- **Free GitHub Actions** — runs stay short and 4-hourly.
- **Respectful scraping** — descriptive User-Agent + delays.
