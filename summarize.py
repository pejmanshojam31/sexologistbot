"""
Summarizes a paper abstract in plain English, then translates that summary
into Farsi. Uses the Anthropic API directly (pip install anthropic).
"""
import json
import os

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
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)
