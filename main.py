"""Orchestrator: fetch all sources -> normalize -> filter -> dedupe -> send.

Run modes:
    python main.py               # fetch, filter, send alerts
    python main.py --dry-run     # fetch + filter only, print what would be sent
"""

import argparse
import logging
import time

from config import CHANNEL_IDS, REQUEST_DELAY_SECONDS
from database import init_db, is_duplicate, mark_sent
from filters import extract_tags, filter_listing, route_channel
from sources import ALL_SOURCES
from telegram_sender import format_message, send_message

logger = logging.getLogger("main")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def fetch_all():
    """Run every source scraper; a broken source must not crash the run."""
    all_listings = []
    for name, fetch_fn in ALL_SOURCES:
        try:
            listings = fetch_fn()
            if not isinstance(listings, list):
                logger.warning("Source %s did not return a list", name)
                listings = []
            listings = [l for l in listings if l]
            logger.info("Source %-11s returned %d listings", name, len(listings))
            all_listings.extend(listings)
        except Exception:
            logger.warning("Source %s crashed - continuing", name, exc_info=True)
        time.sleep(REQUEST_DELAY_SECONDS)
    return all_listings


def main():
    parser = argparse.ArgumentParser(description="Hackathon / tech-contest alert bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and filter but do not send any Telegram messages",
    )
    args = parser.parse_args()

    setup_logging()
    init_db()

    all_listings = fetch_all()
    logger.info("Total fetched: %d", len(all_listings))

    passed = []
    for listing in all_listings:
        listing["tags"] = extract_tags(listing) or listing.get("tags") or []
        if filter_listing(listing):
            passed.append(listing)
    logger.info("Total passed filter: %d", len(passed))

    sent_by_channel = {}
    skipped_duplicates = 0

    for listing in passed:
        channel = route_channel(listing)

        if is_duplicate(listing["url"]):
            skipped_duplicates += 1
            logger.info("Duplicate, skipping: %s", listing["url"])
            continue

        text = format_message(listing)
        if args.dry_run:
            logger.info("[DRY-RUN] would send to %s: %s", channel, listing["url"])
            continue

        chat_id = CHANNEL_IDS.get(channel)
        if send_message(chat_id, text):
            mark_sent(listing["url"], channel)
            sent_by_channel[channel] = sent_by_channel.get(channel, 0) + 1
            logger.info("Sent to %s: %s", channel, listing["title"])
        else:
            logger.error("Failed to send: %s", listing["url"])

    summary = {
        "fetched": len(all_listings),
        "passed_filter": len(passed),
        "sent": sent_by_channel,
        "skipped_duplicates": skipped_duplicates,
    }
    logger.info("Run summary: %s", summary)
    if args.dry_run:
        logger.info("Dry run complete - no messages were sent.")


if __name__ == "__main__":
    main()
