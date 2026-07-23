"""
Posts the finished summary to a Telegram channel via the Bot API.
Setup: message @BotFather on Telegram -> /newbot -> get the token.
Then add the bot as an ADMIN of your channel (needed to post).

Uses HTML parse mode rather than Markdown: paper titles routinely contain
underscores, asterisks and brackets, which Telegram's Markdown parser rejects
with a 400. HTML only needs &, < and > escaped.
"""
from __future__ import annotations  # `list | None` annotations on Python 3.9

import html
import os
import re

import requests

# Telegram rejects messages over 4096 characters.
MAX_LEN = 4096


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


DEFAULT_HASHTAGS = ["#پژوهش_جنسی"]
FILM_HASHTAGS = ["#سینمای_اروتیک"]

# Telegram ends a hashtag at the first character that isn't a letter, digit or
# underscore. Persian text is full of ZWNJ (U+200C, as in می‌شود), which would
# silently truncate a tag, so it becomes an underscore rather than a break.
_TAG_SEPARATORS = re.compile(r"[\s‌‏‎]+")
_TAG_INVALID = re.compile(r"[^\w؀-ۿ]", re.UNICODE)


def clean_hashtag(tag: str) -> str:
    tag = _TAG_SEPARATORS.sub("_", tag.strip().lstrip("#"))
    tag = _TAG_INVALID.sub("", tag).strip("_")
    return f"#{tag}" if tag else ""


def hashtag_line(summary: dict, defaults: list | None = None) -> str:
    tags = summary.get("hashtags_fa") or []
    cleaned = [t for t in (clean_hashtag(x) for x in tags) if t]
    for fallback in DEFAULT_HASHTAGS if defaults is None else defaults:
        if fallback not in cleaned:
            cleaned.append(fallback)
    # dict.fromkeys keeps first-seen order while dropping duplicates
    return " ".join(dict.fromkeys(cleaned))


def article_link(paper: dict) -> str:
    """Publisher's article page (via DOI) when we have one, else PubMed."""
    return paper.get("journal_url") or paper["url"]


def _fa_digits(value) -> str:
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def build_message(paper: dict, summary_en: str, summary_fa: str, hashtags: str = "") -> str:
    """Channel post. Farsi only -- summary_en is kept for the blog, not posted."""
    link = article_link(paper)

    byline = f"<i>{_esc(paper['journal'])}, {_esc(paper['year'])}</i>"
    if paper.get("cited_by"):
        # Only set for archive picks, where the citation count is the point.
        byline += f"\n<i>🔗 {_fa_digits(paper['cited_by'])} استناد</i>"
    header = f"📄 <b>{_esc(paper['title'])}</b>\n{byline}\n\n"

    footer = f'\n\n<a href="{_esc(link)}">مطالعه‌ی مقاله</a>'
    if hashtags:
        footer += f"\n\n{_esc(hashtags)}"
    body = _esc(summary_fa)

    budget = MAX_LEN - len(header) - len(footer)
    if len(body) > budget:
        body = body[: max(budget - 1, 0)].rstrip() + "…"
    return header + body + footer


def build_film_message(film: dict, summary_fa: str, hashtags: str = "") -> str:
    byline_parts = [p for p in (film.get("director"), film.get("country")) if p]
    title = film["title"]
    if film.get("original_title"):
        title += f" · {film['original_title']}"

    message = f"🎬 <b>{_esc(title)} ({_fa_digits(film['year'])})</b>\n"
    if byline_parts:
        message += f"<i>{_esc(' — '.join(byline_parts))}</i>\n"
    message += f"\n{_esc(summary_fa)}"

    if film.get("url"):
        message += f'\n\n<a href="{_esc(film["url"])}">اطلاعات بیشتر</a>'
    if hashtags:
        message += f"\n\n{_esc(hashtags)}"

    return message if len(message) <= MAX_LEN else message[: MAX_LEN - 1].rstrip() + "…"


def post_film_to_telegram(film: dict, summary_fa: str, hashtags: str = "") -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHANNEL_ID"]

    payload = {
        "chat_id": chat_id,
        "text": build_film_message(film, summary_fa, hashtags),
        "parse_mode": "HTML",
    }
    if film.get("url"):
        payload["link_preview_options"] = {
            "url": film["url"],
            "prefer_large_media": True,
            "show_above_text": True,
        }

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=30
    )
    if not resp.ok:
        raise RuntimeError(f"Telegram API error {resp.status_code}: {resp.text}")
    return resp.json()["result"]["message_id"]


def post_to_telegram(paper: dict, summary_en: str, summary_fa: str, hashtags: str = "") -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHANNEL_ID"]

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": build_message(paper, summary_en, summary_fa, hashtags),
            "parse_mode": "HTML",
            # Pull the preview from the publisher's page and show it large,
            # above the text, so each post leads with that paper's own figure.
            "link_preview_options": {
                "url": article_link(paper),
                "prefer_large_media": True,
                "show_above_text": True,
            },
        },
        timeout=30,
    )
    if not resp.ok:
        # Telegram puts the actual reason in the body; raise_for_status hides it.
        raise RuntimeError(f"Telegram API error {resp.status_code}: {resp.text}")
    return resp.json()["result"]["message_id"]
