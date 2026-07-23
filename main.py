"""
Daily pipeline entry point.

Run manually:      python main.py
Run on a schedule:  see .github/workflows/daily.yml (GitHub Actions, free)
                     or add a cron line, e.g.:
                     0 9 * * *  cd /path/to/sexresearch-bot && python main.py
"""
import json
import os

import yaml
from dotenv import load_dotenv

from fetch_papers import fetch_candidates
from post_blog import publish_markdown, publish_wordpress
from post_telegram import post_to_telegram
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


def main() -> None:
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    posted_ids = load_posted_ids()

    print(f"Searching {len(cfg['journals'])} journals, last {cfg['lookback_days']} day(s)...")
    candidates = fetch_candidates(cfg["journals"], cfg["keywords"], cfg["lookback_days"])
    candidates = [p for p in candidates if p["pmid"] not in posted_ids]
    print(f"Found {len(candidates)} new keyword-matching paper(s).")

    if not candidates:
        print("Nothing new to post. Done.")
        return

    for paper in candidates[: cfg["max_posts_per_run"]]:
        print(f"Processing: {paper['title'][:80]}...")
        result = summarize_and_translate(paper)
        summary_en, summary_fa = result["summary_en"], result["summary_fa"]

        post_to_telegram(paper, summary_en, summary_fa)
        print("  -> posted to Telegram")

        if cfg["publish_target"] == "wordpress":
            link = publish_wordpress(paper, summary_en, summary_fa)
            print(f"  -> posted to WordPress: {link}")
        else:
            path = publish_markdown(paper, summary_en, summary_fa)
            print(f"  -> wrote {path}")

        save_posted_id(paper["pmid"])

    print("Done.")


if __name__ == "__main__":
    main()
