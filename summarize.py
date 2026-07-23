"""
Summarizes a paper abstract in plain English, then writes a longer, more
detailed Farsi version for the channel's main audience.

Two backends, chosen by `summarizer:` in config/settings.yaml:

- "you"       -- You.com Research API (YOU_API_KEY). Fast and inexpensive.
- "anthropic" -- Anthropic API (ANTHROPIC_API_KEY), pay-per-use.

The Farsi summary is deliberately longer than the English one: it carries the
method, sample size, the specific findings, what was *not* significant, and the
practical takeaway. The English text is a short header for the same content.
"""
import json
import os
import re

MODEL = "claude-sonnet-5"  # anthropic backend only; "claude-haiku-4-5-20251001" is cheaper

INSTRUCTIONS = """You summarize academic papers on human sexuality for a general \
audience reading a Telegram channel. Be accurate, neutral, and clinical in tone \
-- never sensational. Use ONLY the abstract provided. Do not search for outside \
information and do not invent findings that aren't in the abstract.

Write TWO summaries:

1. summary_en -- 5 to 7 sentences of plain-language English. Cover the
   question, the method and sample, the main findings with their numbers, and
   the takeaway. Not a headline -- a proper short account of the study.

2. summary_fa -- a DETAILED Farsi summary, 10 to 14 sentences, natural and
   fluent (not a word-for-word translation of the English). This is the main
   content for the channel's Farsi-speaking readers, so include:
     - what question the study asked and why it matters
     - the method and sample size (report numbers as given)
     - the specific findings, including which factors mattered most
     - what was measured but did NOT reach significance
     - the practical takeaway, and any limitation the abstract itself states
       (if the abstract states none, simply leave it out -- do not speculate
       about limitations, and do not remark on their absence)
   Use Persian digits for numbers. Prefer "توافق" for consent and
   "رضایت‌مندی" for satisfaction, since plain "رضایت" is ambiguous between the
   two and these papers often contrast them.

3. hashtags_fa -- 3 to 5 Farsi hashtags for this specific paper, so posts can
   be found later by topic. Use underscores instead of spaces (Telegram ends a
   hashtag at the first space). Pick terms a reader would actually search:
   the topic, the population, and the study type, e.g.
   ["#سلامت_جنسی", "#زنان_سالمند", "#کارآزمایی_بالینی"].
   Always include #پژوهش_جنسی as one of them so the whole archive is findable.

Return ONLY a JSON object, no markdown fences, no preamble, with this exact shape:
{"summary_en": "...", "summary_fa": "...", "hashtags_fa": ["#...", "#..."]}"""


def _user_prompt(paper: dict) -> str:
    return f"""Title: {paper['title']}
Journal: {paper['journal']} ({paper['year']})
Abstract: {paper['abstract']}"""


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


def _summarize_you(paper: dict, effort: str = "lite") -> dict:
    import requests

    api_key = os.getenv("YOU_API_KEY")
    if not api_key:
        raise SystemExit(_missing_key_help("YOU_API_KEY", paper))

    resp = requests.post(
        "https://api.you.com/v1/research",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json={
            "input": f"{INSTRUCTIONS}\n\n{_user_prompt(paper)}",
            "research_effort": effort,
        },
        timeout=300,
    )
    if not resp.ok:
        raise RuntimeError(f"You.com API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    for warning in data.get("warnings") or []:
        print(f"  ! You.com warning: {warning}")
    return _parse_json((data.get("output") or {}).get("content", ""))


def _summarize_anthropic(paper: dict) -> dict:
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(_missing_key_help("ANTHROPIC_API_KEY", paper))

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=INSTRUCTIONS,
        messages=[{"role": "user", "content": _user_prompt(paper)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return _parse_json(text)


def _missing_key_help(var: str, paper: dict) -> str:
    return (
        f"{var} is not set, so the summary can't be generated.\n"
        f"Either add it to .env, or write the summary yourself and pass it:\n"
        f"  python main.py --pmid {paper['pmid']} --summary-file your_summary.json\n"
        '  (file format: {"summary_en": "...", "summary_fa": "..."})'
    )


def summarize_and_translate(paper: dict, backend: str = "you", effort: str = "lite") -> dict:
    if backend == "you":
        return _summarize_you(paper, effort)
    if backend == "anthropic":
        return _summarize_anthropic(paper)
    raise SystemExit(f"Unknown summarizer {backend!r}; use 'you' or 'anthropic'.")
