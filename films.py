"""
The channel's film strand: erotic cinema written up in the same analytical
register as the papers.

Kept separate from the paper pipeline on purpose -- there's no PubMed here,
just a curated list in config/films.yaml that you maintain by hand. Films are
posted one per run, in list order, tracked in data/posted_films.json.
"""
from __future__ import annotations

import json
import os

import yaml

FILMS_PATH = "config/films.yaml"
POSTED_LOG = "data/posted_films.json"


def film_id(film: dict) -> str:
    """Stable key for the posted log, so reordering the YAML doesn't repost."""
    return f"{film['title']} ({film['year']})"


def load_posted() -> set:
    if not os.path.exists(POSTED_LOG):
        return set()
    with open(POSTED_LOG, encoding="utf-8") as f:
        return set(json.load(f))


def save_posted(fid: str) -> None:
    ids = load_posted()
    ids.add(fid)
    os.makedirs(os.path.dirname(POSTED_LOG), exist_ok=True)
    with open(POSTED_LOG, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2, ensure_ascii=False)


def load_films() -> list[dict]:
    with open(FILMS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f).get("films", [])


def next_film(title: str | None = None) -> dict | None:
    """The named film, or the first one not yet posted."""
    films = load_films()
    if title:
        wanted = title.strip().lower()
        for film in films:
            if film["title"].strip().lower() == wanted:
                return film
        raise SystemExit(
            f"No film titled {title!r} in {FILMS_PATH}. Available:\n  "
            + "\n  ".join(f["title"] for f in films)
        )

    posted = load_posted()
    for film in films:
        if film_id(film) not in posted:
            return film
    return None
