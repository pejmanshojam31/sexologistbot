"""
Fetches recent papers from PubMed and returns candidates to summarize.

Two groups of journals, handled differently (see config/settings.yaml):

- topic_journals   -- dedicated sexuality journals. Everything they publish is
                      on topic, so we take all of it, no keyword filter.
- general_journals -- Nature-family and other broad journals. These publish
                      hundreds of papers a day, so the keyword filter is pushed
                      into the PubMed query. Filtering afterwards would not
                      work: esearch would return an arbitrary truncated slice
                      of the day's output before we ever saw the keywords.

PubMed's E-utilities are free and don't require an API key (an optional key
just raises your rate limit). Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""
from __future__ import annotations  # `str | None` annotations on Python 3.9 (macOS system python)

import os
import time
import xml.etree.ElementTree as ET

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RETMAX = 200        # per search; well above a day's output for these journals
EFETCH_BATCH = 150  # ids per efetch request


def _all_text(node) -> str:
    """Flatten an element's text, including text inside nested inline markup."""
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _pause(api_key: str | None) -> None:
    time.sleep(0.35 if not api_key else 0.11)  # stay under NCBI's rate limit


def _esearch(term: str, lookback_days: int, api_key: str | None) -> list[str]:
    """Return PubMed IDs matching a query within the lookback window."""
    params = {
        "db": "pubmed",
        "term": term,
        "reldate": lookback_days,
        "datetype": "pdat",
        "retmax": RETMAX,
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key
    r = requests.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    result = r.json().get("esearchresult", {})

    count = int(result.get("count", 0))
    if count > RETMAX:
        print(f"  ! {count} hits exceeds retmax {RETMAX}; consider a shorter lookback.")
    return result.get("idlist", [])


def _journal_clause(journals: list[str]) -> str:
    return " OR ".join(f'"{j}"[Journal]' for j in journals)


def _keyword_clause(keywords: list[str]) -> str:
    # [tiab] = title/abstract. Quoted so multi-word keywords stay phrases.
    return " OR ".join(f'"{k}"[tiab]' for k in keywords)


def _efetch(pmids: list[str], api_key: str | None) -> list[dict]:
    """Fetch title/abstract/authors/journal/date/doi for a batch of PubMed IDs."""
    if not pmids:
        return []
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    if api_key:
        params["api_key"] = api_key
    r = requests.get(f"{EUTILS}/efetch.fcgi", params=params, timeout=60)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    papers = []
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID", default="")
        title_node = article.find(".//ArticleTitle")
        title = _all_text(title_node)

        # Structured abstracts split into labelled sections (BACKGROUND, METHODS...);
        # itertext keeps text inside inline markup like <i> or <sup>, which .text drops.
        abstract_parts = []
        for node in article.findall(".//Abstract/AbstractText"):
            chunk = _all_text(node)
            if not chunk:
                continue
            label = node.get("Label")
            abstract_parts.append(f"{label.title()}: {chunk}" if label else chunk)
        abstract = " ".join(abstract_parts).strip()

        journal = article.findtext(".//Journal/Title", default="")
        # Some records carry no <Year>, only a free-text MedlineDate like "2024 Jan-Feb".
        pubdate_year = article.findtext(".//JournalIssue/PubDate/Year", default="")
        if not pubdate_year:
            medline_date = article.findtext(".//JournalIssue/PubDate/MedlineDate", default="")
            pubdate_year = medline_date.split()[0] if medline_date else ""

        authors = []
        for a in article.findall(".//AuthorList/Author"):
            last = a.findtext("LastName")
            fore = a.findtext("ForeName")
            if last:
                authors.append(f"{fore} {last}".strip() if fore else last)

        doi = ""
        for eid in article.findall(".//ArticleIdList/ArticleId"):
            if eid.get("IdType") == "doi":
                doi = eid.text or ""

        if not abstract:
            continue  # skip papers with no abstract, nothing to summarize

        papers.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "year": pubdate_year,
                "authors": authors,
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return papers


def _efetch_all(pmids: list[str], api_key: str | None) -> list[dict]:
    papers = []
    for i in range(0, len(pmids), EFETCH_BATCH):
        papers.extend(_efetch(pmids[i : i + EFETCH_BATCH], api_key))
        _pause(api_key)
    return papers


def fetch_by_pmid(pmid: str) -> dict:
    """Fetch a single paper by PubMed ID, bypassing journal/keyword filtering."""
    papers = _efetch([pmid], os.getenv("NCBI_API_KEY") or None)
    if not papers:
        raise ValueError(f"PMID {pmid} not found, or it has no abstract to summarize.")
    return papers[0]


def is_excluded(paper: dict, exclude_keywords: list[str]) -> bool:
    """Drop animal-model and similar off-topic work from the general journals."""
    text = f"{paper['title']} {paper['abstract']}".lower()
    return any(kw.lower() in text for kw in exclude_keywords)


def fetch_candidates(cfg: dict, lookback_days: int) -> list[dict]:
    api_key = os.getenv("NCBI_API_KEY") or None
    exclude = cfg.get("exclude_keywords", [])
    by_pmid: dict[str, dict] = {}

    topic = cfg.get("topic_journals", [])
    if topic:
        print(f"  searching {len(topic)} sexuality journals (no keyword filter)...")
        ids = _esearch(_journal_clause(topic), lookback_days, api_key)
        _pause(api_key)
        for paper in _efetch_all(ids, api_key):
            by_pmid.setdefault(paper["pmid"], paper)

    general = cfg.get("general_journals", [])
    if general:
        print(f"  searching {len(general)} general journals (keyword-filtered)...")
        term = f"({_journal_clause(general)}) AND ({_keyword_clause(cfg['keywords'])})"
        ids = _esearch(term, lookback_days, api_key)
        _pause(api_key)
        for paper in _efetch_all(ids, api_key):
            if is_excluded(paper, exclude):
                continue
            by_pmid.setdefault(paper["pmid"], paper)

    return list(by_pmid.values())
