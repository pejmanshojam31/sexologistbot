"""
Publishes the finished summary to your blog. Two modes, set in config/settings.yaml:

- "markdown": writes a dated .md file with frontmatter into posts/. Point any
  static site generator (Hugo, Jekyll, Astro, Eleventy) at this folder and it
  just works. This is the easiest option if you don't have a blog yet --
  pair it with GitHub Pages for a free, zero-maintenance blog.
- "wordpress": posts directly to an existing WordPress site via its REST API.
"""
import datetime as dt
import os
import re

import requests


def _yaml_str(value: str) -> str:
    """Quote a value for YAML frontmatter. Titles often contain ':' and '"'."""
    return '"' + (value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:80]


def publish_markdown(paper: dict, summary_en: str, summary_fa: str, out_dir: str = "posts") -> str:
    os.makedirs(out_dir, exist_ok=True)
    today = dt.date.today().isoformat()
    slug = _slugify(paper["title"]) or f"paper-{paper['pmid']}"  # titles can be all non-ASCII
    path = os.path.join(out_dir, f"{today}-{slug}.md")

    content = f"""---
title: {_yaml_str(paper['title'])}
date: {today}
journal: {_yaml_str(paper['journal'])}
year: {_yaml_str(paper['year'])}
source_url: {paper['url']}
doi: {_yaml_str(paper['doi'])}
---

## Summary

{summary_en}

## خلاصه فارسی

{summary_fa}

---
Source: [{paper['journal']}]({paper['url']})
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def publish_wordpress(paper: dict, summary_en: str, summary_fa: str) -> str:
    url = os.environ["WORDPRESS_URL"].rstrip("/") + "/wp-json/wp/v2/posts"
    auth = (os.environ["WORDPRESS_USER"], os.environ["WORDPRESS_APP_PASSWORD"])

    body_html = (
        f"<p>{summary_en}</p>"
        f"<h3>خلاصه فارسی</h3><p dir='rtl'>{summary_fa}</p>"
        f"<p><a href='{paper['url']}'>Source: {paper['journal']}</a></p>"
    )
    resp = requests.post(
        url,
        auth=auth,
        json={"title": paper["title"], "content": body_html, "status": "publish"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("link", "")
