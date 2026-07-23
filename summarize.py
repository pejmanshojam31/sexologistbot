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


FILM_INSTRUCTIONS = """You write about erotic cinema for a Telegram channel that \
otherwise covers human sexuality research. Match that register: analytical and \
serious, the way a film-studies writer would treat the material. Not a review, \
not a recommendation, and never titillating or explicit -- describe what the film \
does with sexuality, not what it shows.

Write in Farsi only. 8 to 12 sentences covering:
  - the film, its director and year, and the basic premise in one or two sentences
  - how it treats desire, intimacy or the body, and what makes that treatment
    distinctive
  - its critical reception and any controversy it generated
  - why it matters for understanding sexuality on screen -- the gaze, consent,
    censorship, gender, whatever that particular film raises

Be accurate. If you are unsure of a detail, leave it out rather than guess.
Use Persian digits for years and numbers.

Also give 3 to 5 Farsi hashtags. Use underscores instead of spaces. Always
include #سینمای_اروتیک.

Return ONLY a JSON object, no markdown fences, no preamble, with this shape:
{"summary_fa": "...", "hashtags_fa": ["#...", "#..."]}"""


def _film_prompt(film: dict) -> str:
    lines = [f"Film: {film['title']} ({film['year']})"]
    for key, label in (
        ("original_title", "Original title"),
        ("director", "Director"),
        ("country", "Country"),
        ("note", "Angle to emphasize"),
    ):
        if film.get(key):
            lines.append(f"{label}: {film[key]}")
    return "\n".join(lines)


def summarize_film(film: dict, backend: str = "you", effort: str = "lite") -> dict:
    """Farsi write-up for one film. Same backends as the paper summarizer."""
    required = {"summary_fa"}
    if backend == "you":
        return _call_you(f"{FILM_INSTRUCTIONS}\n\n{_film_prompt(film)}", effort, required)
    if backend == "anthropic":
        return _call_anthropic(FILM_INSTRUCTIONS, _film_prompt(film), required)
    raise SystemExit(f"Unknown summarizer {backend!r}; use 'you' or 'anthropic'.")


def _user_prompt(paper: dict) -> str:
    return f"""Title: {paper['title']}
Journal: {paper['journal']} ({paper['year']})
Abstract: {paper['abstract']}"""


def _parse_json(text: str, required: set) -> dict:
    """Pull the JSON object out of the reply, tolerating fences or a stray preamble."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object in model reply: {text[:200]}")
        data = json.loads(match.group(0))

    missing = required - data.keys()
    if missing:
        raise ValueError(f"Model reply missing key(s): {sorted(missing)}")
    return data


def _call_you(prompt: str, effort: str, required: set) -> dict:
    import requests

    api_key = os.getenv("YOU_API_KEY")
    if not api_key:
        raise SystemExit(_missing_key_help("YOU_API_KEY"))

    resp = requests.post(
        "https://api.you.com/v1/research",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json={"input": prompt, "research_effort": effort},
        timeout=300,
    )
    if not resp.ok:
        raise RuntimeError(f"You.com API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    for warning in data.get("warnings") or []:
        print(f"  ! You.com warning: {warning}")
    return _parse_json((data.get("output") or {}).get("content", ""), required)


def _call_anthropic(system: str, user: str, required: set) -> dict:
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(_missing_key_help("ANTHROPIC_API_KEY"))

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return _parse_json(text, required)


def _missing_key_help(var: str) -> str:
    return (
        f"{var} is not set, so the summary can't be generated.\n"
        f"Add it to .env, or for a paper, write the summary yourself and pass it:\n"
        f"  ./run.sh --pmid <id> --summary-file your_summary.json\n"
        '  (file format: {"summary_en": "...", "summary_fa": "..."})'
    )


def summarize_and_translate(paper: dict, backend: str = "you", effort: str = "lite") -> dict:
    required = {"summary_en", "summary_fa"}
    if backend == "you":
        return _call_you(f"{INSTRUCTIONS}\n\n{_user_prompt(paper)}", effort, required)
    if backend == "anthropic":
        return _call_anthropic(INSTRUCTIONS, _user_prompt(paper), required)
    raise SystemExit(f"Unknown summarizer {backend!r}; use 'you' or 'anthropic'.")
