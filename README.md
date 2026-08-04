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

- **16 sources scraped:** Devfolio, Unstop, Reskilll, Internshala, Devpost,
  lablab.ai, MLH, CodeChef, HackerRank, **Kaggle**, **Codeforces**, **AtCoder**,
  **HackerEarth**, **ETHGlobal**, **AIcrowd**, **MyGov / Innovate India** —
  hackathons, coding contests, AI/ML competitions, Web3 hackathons and
  government challenges, including real **cash-prize** competitions (Kaggle
  prizes up to $850K)
- **Rule-based filtering:** prize threshold, deadline not passed, location
  exclusions, and optional keyword match — configurable in `config.py`
  (`REQUIRE_KEYWORD_MATCH = False` alerts every tech contest)
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
│   ├── hackerrank.py          # hackerrank.com contests (public API)
│   ├── kaggle.py              # kaggle.com competitions (official API, token)
│   ├── codeforces.py          # codeforces.com contests (public API)
│   ├── atcoder.py             # atcoder.jp contests
│   ├── hackerearth.py         # hackerearth.com events (public JSON)
│   ├── ethglobal.py           # ethglobal.com/events
│   ├── aicrowd.py             # aicrowd.com/challenges
│   └── mygov.py               # innovateindia.mygov.in challenges
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
   - Prize rule (three tiers): listed prize `>= MIN_PRIZE_INR` (INR) or
     `>= MIN_PRIZE_USD` (USD) always passes; no prize shown → passes only if
     the source is in `LIKELY_CASH_SOURCES` (platforms whose events normally
     award cash) or `PASS_UNKNOWN_PRIZE` is `True`
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
| `KAGGLE_API_TOKEN` | optional — enables Kaggle cash-prize alerts (free from kaggle.com → Settings → API) |

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
| `PASS_UNKNOWN_PRIZE` | `False` | Allow listings with no prize info at all (every source, even no-prize ones) |
| `PASS_LIKELY_CASH_PRIZE` | `True` | Let no-prize listings through when their source normally awards cash prizes |
| `LIKELY_CASH_SOURCES` | `{devfolio, devpost, unstop, lablab, mlh, reskilll, codechef, hackerrank}` | Sources treated as "likely cash" when no amount is shown |
| `REQUIRE_KEYWORD_MATCH` | `False` | Require a `KEYWORDS` term in the title. `False` = alert every tech contest from these tech-only platforms |
| `KEYWORDS` | `["ai", "blockchain", ...]` | At least one must match the title/tags |
| `EXCLUDE_LOCATIONS` | `[]` | Drop listings whose location matches |
| `REQUEST_DELAY_SECONDS` | `1.5` | Politeness delay between HTTP requests |
| `MAX_PAGES_PER_SOURCE` | `3` | Max pages crawled per paginated source |

---

## Sources & known limitations

- **Devpost** — uses its JSON API (`devpost.com/api/hackathons`).
- **MLH** — parses schema.org microdata on the season page. MLH doesn't publish
  prize amounts, so these have `prize_value=None` and alert via the
  `LIKELY_CASH_SOURCES` rule (collegiate hackathons usually have prizes).
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
- **Kaggle** — official API (`/api/v1/competitions/list`) with your free
  `KAGGLE_API_TOKEN`. Real prize money (USD/INR). Only cash-prize competitions
  are kept — "Knowledge"/"Swag" rewards are dropped.
- **Internshala** — parses competition cards. Internshala **frequently blocks bots**
  (HTTP 403). When blocked it logs a warning and returns nothing — the run
  continues. Seeing 0 Internshala listings is the block, not a bug.
- **Codeforces** — public API (`/api/contest.list`); only upcoming (`BEFORE`)
  contests. No prizes in the feed → alert via `LIKELY_CASH_SOURCES`.
- **AtCoder** — parses the upcoming table on `atcoder.jp/contests` (needs a
  browser User-Agent). No prizes in the feed → alert via `LIKELY_CASH_SOURCES`.
- **HackerEarth** — public events JSON (`/chrome-extension/events/`). Usually
  low volume; prizes are on the detail page → alert via `LIKELY_CASH_SOURCES`.
- **ETHGlobal** — parses the events card list on `ethglobal.com/events`. Only
  hackathon/summit events are kept (conferences/coworking are dropped). Prize
  amounts aren't on the list page → alert via `LIKELY_CASH_SOURCES`.
- **AIcrowd** — parses `aicrowd.com/challenges`; only challenges still running
  (status text like "Phase 1: 4 days left") are kept, and the deadline is
  derived from that text. Prizes are on the detail page → `LIKELY_CASH_SOURCES`.
- **MyGov / Innovate India** — scrapes `innovateindia.mygov.in` challenge pages
  (government challenges/grants). Low volume; some pages have no parseable
  deadline, so they pass the deadline filter.

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

## 🎓 University Intelligence (new module)

A **drop-in module** that monitors official public university sources — news
pages, event pages, innovation cells, incubation centres, startup cells,
training & placement pages, department announcements, research centres,
official RSS feeds and public calendars — and posts **student opportunities**
(hackathons, coding contests, ideathons, startup/innovation challenges, AI
competitions, workshops, bootcamps, internships, grants, scholarships,
conferences, tech fests) through the **same Telegram pipeline** as the main bot.

It does **not** touch any existing module. Everything lives under
`university_intel/` and its tables live in the same `data/sent_listings.db`.

### How it works

```
public university pages (RSS / events / news / innovation / sitemap)
        │  async aiohttp scans (polite delay, retries)
        ▼
raw items ──► classifier + ignore filter (admissions, exams, results,
        │     tenders, recruitment, circulars → dropped)
        ▼
dedupe (URL hash · main-bot store · title similarity · date)
        ▼
store in `events` table ──► publish via existing send_message()
```

### What the module provides

| Piece | File |
|---|---|
| DB tables `universities`, `sources`, `events` | `university_intel/db.py` |
| Async HTTP client (aiohttp, delay + retries) | `university_intel/http.py` |
| Adapters: RSS, events page, news, innovation, announcements, generic | `university_intel/adapters/` |
| Auto-discovery of event/RSS/innovation pages from homepages | `university_intel/discovery.py` |
| 15-category classifier + ignore filter | `university_intel/classifier.py` |
| Dedup (URL hash / title fuzzy / date / semantic) | `university_intel/dedupe.py`, `semantic.py` |
| Publishing via existing `telegram_sender` | `university_intel/publisher.py` |
| 30-min scheduler + retries + logs | `university_intel/scheduler.py`, `logging.py` |
| Telegram admin commands | `university_intel/admin.py` |
| Worker entry point (`--once` / daemon) | `university_intel/worker.py` |
| Telangana seed list (44 institutions) | `university_intel/seeds.py` |
| Unit tests | `tests/` |

### Run it

**GitHub Actions (free, zero setup)** — add a `university_scan.yml` workflow
(already included) that runs `python -m university_intel.worker --once` every
4 hours on the free tier. It shares your existing `BOT_TOKEN` secret. The
existing `run_bot.yml` is untouched.

> ⚠️ GitHub Actions can't do a true 30-minute cadence inside the free minute
> budget, and short-lived jobs can't listen for Telegram commands.

**Docker daemon (true 30-min + admin commands)** — for a real every-30-min
loop with `/adduniversity` etc., run the container on any always-on machine:

```bash
docker compose up -d --build
```

Free always-on options: Oracle Cloud **Always Free** VM, or your own always-on
PC/laptop. Logs: `data/university_logs/bot.log`.

### Admin commands

Set `ADMIN_CHAT_IDS` (comma-separated numeric chat IDs) in `.env`. The listener
uses the **same** bot token — safe because the existing bot never calls
`getUpdates`.

```
/adduniversity <name> <website> [state] [city]   # add + auto-discover pages
/removeuniversity <name>
/listuniversities
/scan <name>          # scan one university now
/forcescan            # scan everything with forced discovery
/stats
/help
```

### Key config (.env)

| Variable | Default | Meaning |
|---|---|---|
| `SCAN_INTERVAL` | `30` | Minutes between daemon scans |
| `ADMIN_CHAT_IDS` | empty | Chat IDs allowed to run commands |
| `SEED_ON_EMPTY` | `true` | Auto-load the Telangana seed list |
| `ENABLE_DISCOVERY` | `true` | Auto-find event/RSS pages from homepages |
| `PUBLISH_OTHER_CATEGORY` | `false` | Publish unclassifiable announcements |
| `REQUIRE_TITLE_SIGNAL` | `true` | Only publish titles that signal an opportunity |
| `UNIVERSITY_REQUIRE_PRIZE` | `true` | Only publish prize-money opportunities (announcement mentions a prize, or it's a prize-awarding category like hackathons/contests). Plain workshops/conferences/bootcamps are dropped. |
| `SEMANTIC_PROVIDER` | `local` | `local` (free) or `grok` (paid xAI API) |

### Adding other states later

Just add entries with a different `state` to `seeds.py` (or use
`/adduniversity` with a state). The classifier, adapters, discovery and channel
routing all read `state`, so nothing else changes.

---

## Constraints honored

- **$0** — no paid hosting, no paid APIs.
- **No AI/LLM** — pure rule-based filtering.
- **Free GitHub Actions** — runs stay short and 4-hourly.
- **Respectful scraping** — descriptive User-Agent + delays.
