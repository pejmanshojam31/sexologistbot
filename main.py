"""
Daily pipeline entry point.

Run manually:      python main.py
Preview only:      python main.py --dry-run
One specific paper: python main.py --pmid 42479982
Skip the API and use a hand-written summary:
                    python main.py --pmid 42479982 --summary-file examples/42479982.json

Run on a schedule:  see .github/workflows/daily.yml (GitHub Actions, free)
                     or add a cron line, e.g.:
                     0 9 * * *  cd /path/to/sexresearch-bot && python main.py
"""
from __future__ import annotations  # `dict | None` annotations on Python 3.9

import argparse
import json
import os

import yaml
from dotenv import load_dotenv

from fetch_papers import fetch_by_pmid, fetch_candidates
from post_blog import publish_markdown, publish_wordpress
from post_telegram import build_message, post_to_telegram
from summarize import summarize_and_translate

load_dotenv()

CONFIG_PATH = "config/settings.yaml"
POSTED_LOG = "data/posted_ids.json"


def load_posted_ids() -> set:
    if not os.path.exists(POSTED_LOG):
        return set()
    with open(POSTED_LOG) as f:
        return set(json.load(f))


def save_posted_id(pmid: str) -> None:
    ids = load_posted_ids()
    ids.add(pmid)
    os.makedirs(os.path.dirname(POSTED_LOG), exist_ok=True)
    with open(POSTED_LOG, "w") as f:
        json.dump(sorted(ids), f, indent=2)


def process(paper: dict, cfg: dict, summary: dict | None = None, dry_run: bool = False) -> None:
    """Summarize (unless one is supplied), then post to Telegram and the blog."""
    result = summary or summarize_and_translate(paper)
    summary_en, summary_fa = result["summary_en"], result["summary_fa"]

    if dry_run:
        print("\n--- Telegram message (dry run, nothing sent) ---")
        print(build_message(paper, summary_en, summary_fa))
        print("--- end ---\n")
        return

    message_id = post_to_telegram(paper, summary_en, summary_fa)
    handle = os.getenv("TELEGRAM_CHANNEL_ID", "").lstrip("@")
    where = f"https://t.me/{handle}/{message_id}" if not handle.startswith("-") else f"message {message_id}"
    print(f"  -> posted to Telegram: {where}")

    if cfg["publish_target"] == "wordpress":
        print(f"  -> posted to WordPress: {publish_wordpress(paper, summary_en, summary_fa)}")
    else:
        print(f"  -> wrote {publish_markdown(paper, summary_en, summary_fa)}")

    save_posted_id(paper["pmid"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Post a summarized sex-research paper.")
    ap.add_argument("--pmid", help="post one specific PubMed ID instead of searching")
    ap.add_argument("--dry-run", action="store_true", help="print the message, post nothing")
    ap.add_argument(
        "--summary-file",
        help="JSON file with summary_en/summary_fa; skips the Anthropic API call",
    )
    ap.add_argument("--lookback", type=int, help="override lookback_days (useful for backfill)")
    args = ap.parse_args()

    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    summary = None
    if args.summary_file:
        with open(args.summary_file, encoding="utf-8") as f:
            summary = json.load(f)
        missing = {"summary_en", "summary_fa"} - summary.keys()
        if missing:
            raise SystemExit(f"{args.summary_file} is missing key(s): {sorted(missing)}")

    if args.pmid:
        paper = fetch_by_pmid(args.pmid)
        print(f"Processing: {paper['title'][:80]}...")
        process(paper, cfg, summary=summary, dry_run=args.dry_run)
        print("Done.")
        return

    posted_ids = load_posted_ids()
    lookback = args.lookback or cfg["lookback_days"]

    print(f"Searching {len(cfg['journals'])} journals, last {lookback} day(s)...")
    candidates = fetch_candidates(cfg["journals"], cfg["keywords"], lookback)
    candidates = [p for p in candidates if p["pmid"] not in posted_ids]
    print(f"Found {len(candidates)} new keyword-matching paper(s).")

    if not candidates:
        print("Nothing new to post. Done.")
        return

    for paper in candidates[: cfg["max_posts_per_run"]]:
        print(f"Processing: {paper['title'][:80]}...")
        process(paper, cfg, dry_run=args.dry_run)

    print("Done.")


if __name__ == "__main__":
    main()
