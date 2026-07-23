"""
Summarizes a paper abstract in plain English, then translates that summary
into Farsi. Uses the Anthropic API directly (pip install anthropic).
"""
import json
import os
import re

import anthropic

MODEL = "claude-sonnet-5"  # swap to "claude-haiku-4-5-20251001" for a cheaper/faster run

SYSTEM_PROMPT = """You summarize academic papers on human sexuality for a general \
audience reading a Telegram channel. Be accurate, neutral, and clinical in tone \
-- never sensational. Do not invent findings that aren't in the abstract.

Return ONLY a JSON object, no markdown fences, no preamble, with this exact shape:
{
  "summary_en": "2-4 sentence plain-language summary in English",
  "summary_fa": "the same summary translated into natural, fluent Farsi"
}"""


def summarize_and_translate(paper: dict) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set, so the summary can't be generated.\n"
            "Either add a funded key to .env, or write the summary yourself and pass it:\n"
            f"  python main.py --pmid {paper['pmid']} --summary-file your_summary.json\n"
            '  (file format: {"summary_en": "...", "summary_fa": "..."})'
        )
    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = f"""Title: {paper['title']}
Journal: {paper['journal']} ({paper['year']})
Abstract: {paper['abstract']}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    return _parse_json(text)


def _parse_json(text: str) -> dict:
    """Pull the JSON object out of the reply, tolerating fences or a stray preamble."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object in model reply: {text[:200]}")
        data = json.loads(match.group(0))

    missing = {"summary_en", "summary_fa"} - data.keys()
    if missing:
        raise ValueError(f"Model reply missing key(s): {sorted(missing)}")
    return data
