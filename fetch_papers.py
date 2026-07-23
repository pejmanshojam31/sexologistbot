"""
Fetches recent papers from PubMed for the configured journals, filters them
by keyword, and returns candidates that haven't been posted yet.

PubMed's E-utilities are free and don't require an API key (an optional key
just raises your rate limit). Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""
from __future__ import annotations  # `str | None` annotations on Python 3.9 (macOS system python)

import os
import time
import xml.etree.ElementTree as ET

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _all_text(node) -> str:
    """Flatten an element's text, including text inside nested inline markup."""
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _esearch(journal: str, lookback_days: int, api_key: str | None) -> list[str]:
    """Return PubMed IDs published in the given journal within the lookback window."""
    params = {
        "db": "pubmed",
        "term": f'"{journal}"[Journal]',
        "reldate": lookback_days,
        "datetype": "pdat",
        "retmax": 50,
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key
    r = requests.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def _efetch(pmids: list[str], api_key: str | None) -> list[dict]:
    """Fetch title/abstract/authors/journal/date/doi for a batch of PubMed IDs."""
    if not pmids:
        return []
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    if api_key:
        params["api_key"] = api_key
    r = requests.get(f"{EUTILS}/efetch.fcgi", params=params, timeout=30)
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


def fetch_by_pmid(pmid: str) -> dict:
    """Fetch a single paper by PubMed ID, bypassing journal/keyword filtering."""
    papers = _efetch([pmid], os.getenv("NCBI_API_KEY") or None)
    if not papers:
        raise ValueError(f"PMID {pmid} not found, or it has no abstract to summarize.")
    return papers[0]


def keyword_match(paper: dict, keywords: list[str]) -> bool:
    text = f"{paper['title']} {paper['abstract']}".lower()
    return any(kw.lower() in text for kw in keywords)


def fetch_candidates(journals: list[str], keywords: list[str], lookback_days: int) -> list[dict]:
    api_key = os.getenv("NCBI_API_KEY") or None
    by_pmid: dict[str, dict] = {}
    for journal in journals:
        pmids = _esearch(journal, lookback_days, api_key)
        time.sleep(0.35 if not api_key else 0.11)  # stay under NCBI's rate limit
        for paper in _efetch(pmids, api_key):
            by_pmid.setdefault(paper["pmid"], paper)  # same paper can match two journals
        time.sleep(0.35 if not api_key else 0.11)

    return [p for p in by_pmid.values() if keyword_match(p, keywords)]
