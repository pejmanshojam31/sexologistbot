"""
Finds the most-cited papers from earlier years, for days when nothing new has
been published (and to build up an archive of landmark work).

PubMed has no citation data at all, so this uses Europe PMC, which exposes
`citedByCount` and can sort by it. We only take the PMIDs from Europe PMC and
then fetch the full records through fetch_papers, so every paper reaching the
rest of the pipeline has the same shape and the same XML parsing behind it.
"""
from __future__ import annotations

import requests

from fetch_papers import fetch_by_pmid, is_excluded

EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _query(cfg: dict, year_from: int, year_to: int) -> str:
    """
    Same two-tier logic as the daily search, and for the same reason: the
    general journals must be keyword-constrained. Without that, "most cited
    paper in Nature Communications" is a bioinformatics tool with 11k
    citations, not a sexuality paper.
    """
    topic = " OR ".join(f'JOURNAL:"{j}"' for j in cfg.get("topic_journals", []))
    general = " OR ".join(f'JOURNAL:"{j}"' for j in cfg.get("general_journals", []))
    keywords = " OR ".join(
        f'(TITLE:"{k}" OR ABSTRACT:"{k}")' for k in cfg.get("keywords", [])
    )

    scopes = []
    if topic:
        scopes.append(f"({topic})")
    if general and keywords:
        scopes.append(f"(({general}) AND ({keywords}))")
    scope = " OR ".join(scopes)

    return f"({scope}) AND (PUB_YEAR:[{year_from} TO {year_to}]) AND HAS_ABSTRACT:Y"


def top_cited_pmids(
    cfg: dict, year_from: int, year_to: int, page_size: int = 100
) -> list[tuple[str, int]]:
    """Return (pmid, citation_count) for the most-cited papers, highest first."""
    r = requests.get(
        EUROPEPMC,
        params={
            "query": _query(cfg, year_from, year_to),
            "format": "json",
            "pageSize": page_size,
            "sort": "CITED desc",
            "resultType": "core",
        },
        timeout=60,
    )
    r.raise_for_status()

    out = []
    for item in r.json().get("resultList", {}).get("result", []):
        pmid = item.get("pmid")
        if pmid:  # some records are PMC-only and have no PubMed id
            out.append((pmid, item.get("citedByCount") or 0))
    return out


def fetch_top_cited(cfg: dict, year_from: int, year_to: int, exclude: set[str]) -> dict | None:
    """Most-cited paper from the given years that hasn't been posted yet."""
    for pmid, cited in top_cited_pmids(cfg, year_from, year_to):
        if pmid in exclude:
            continue
        try:
            paper = fetch_by_pmid(pmid)
        except ValueError:
            continue  # no abstract in PubMed's copy; try the next one
        if is_excluded(paper, cfg.get("exclude_keywords", [])):
            continue  # animal work, same filter the daily search uses
        paper["cited_by"] = cited
        return paper
    return None
