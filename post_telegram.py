"""
Posts the finished summary to a Telegram channel via the Bot API.
Setup: message @BotFather on Telegram -> /newbot -> get the token.
Then add the bot as an ADMIN of your channel (needed to post).
"""
import os

import requests


def post_to_telegram(paper: dict, summary_en: str, summary_fa: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHANNEL_ID"]

    text = (
        f"📄 *{paper['title']}*\n"
        f"_{paper['journal']}, {paper['year']}_\n\n"
        f"{summary_en}\n\n"
        f"🔹 *خلاصه فارسی:*\n{summary_fa}\n\n"
        f"[Read the paper]({paper['url']})"
    )

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    resp.raise_for_status()
