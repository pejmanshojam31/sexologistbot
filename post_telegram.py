"""
Posts the finished summary to a Telegram channel via the Bot API.
Setup: message @BotFather on Telegram -> /newbot -> get the token.
Then add the bot as an ADMIN of your channel (needed to post).

Uses HTML parse mode rather than Markdown: paper titles routinely contain
underscores, asterisks and brackets, which Telegram's Markdown parser rejects
with a 400. HTML only needs &, < and > escaped.
"""
import html
import os

import requests

# Telegram rejects messages over 4096 characters.
MAX_LEN = 4096


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def article_link(paper: dict) -> str:
    """Publisher's article page (via DOI) when we have one, else PubMed."""
    return paper.get("journal_url") or paper["url"]


def build_message(paper: dict, summary_en: str, summary_fa: str) -> str:
    link = article_link(paper)
    header = (
        f"📄 <b>{_esc(paper['title'])}</b>\n"
        f"<i>{_esc(paper['journal'])}, {_esc(paper['year'])}</i>\n\n"
    )
    footer = f'\n\n<a href="{_esc(link)}">Read the paper</a>'
    body = f"{_esc(summary_en)}\n\n🔹 <b>خلاصه فارسی:</b>\n{_esc(summary_fa)}"

    budget = MAX_LEN - len(header) - len(footer)
    if len(body) > budget:
        body = body[: max(budget - 1, 0)].rstrip() + "…"
    return header + body + footer


def post_to_telegram(paper: dict, summary_en: str, summary_fa: str) -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHANNEL_ID"]

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": build_message(paper, summary_en, summary_fa),
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
