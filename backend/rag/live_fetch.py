"""Live fetch of ShareTechnote / 3GPP pages to supplement static RAG."""

from __future__ import annotations

import re
from typing import Any

from .ingest import extract_title, fetch_html, html_to_text

_SHARETECH = re.compile(r"sharetechnote\.com", re.I)
_3GPP = re.compile(r"3gpp\.org", re.I)
_TOPIC_RE = re.compile(r"\b(prach|rach|pdcch|pdsch|pusch|pucch|ssb|numerology|mimo|beam|endc|nr)\b", re.I)


def guess_sharetechnote_url(query: str) -> str | None:
    """Guess a ShareTechnote 5G page from query terms."""
    ql = query.lower()
    slug_map = {
        "prach": "PRACH",
        "rach": "RACH",
        "pdcch": "PDCCH",
        "pdsch": "PDSCH",
        "pusch": "PUSCH",
        "pucch": "PUCCH",
        "ssb": "SSB",
        "numerology": "Numerology",
        "mimo": "MIMO",
        "beam management": "BeamManagement",
        "beam": "BeamManagement",
        "en-dc": "EN_DC",
        "endc": "EN_DC",
        "frame structure": "FrameStructure",
        "framestructure": "FrameStructure",
    }
    for term, slug in slug_map.items():
        if term in ql:
            return f"https://www.sharetechnote.com/html/5G/5G_{slug}.html"
    m = _TOPIC_RE.search(query)
    if m:
        slug = m.group(1).upper()
        if slug == "BEAM":
            return "https://www.sharetechnote.com/html/5G/5G_BeamManagement.html"
        if slug == "NR":
            return "https://www.sharetechnote.com/html/5G/Handbook_5G_Index.html"
        return f"https://www.sharetechnote.com/html/5G/5G_{slug}.html"
    return None


def fetch_page_excerpt(url: str, *, max_chars: int = 3500) -> dict[str, Any]:
    """Fetch and return live page text excerpt."""
    html = fetch_html(url, timeout=12)
    text = html_to_text(html)
    title = extract_title(html, url)
    if not text.strip():
        return {"ok": False, "url": url, "error": "empty page"}
    return {
        "ok": True,
        "url": url,
        "title": title,
        "text": text[:max_chars],
        "live": True,
        "source": "live_fetch",
    }


def fetch_live_for_query(query: str, rag_cites: list[dict] | None = None) -> tuple[str, list[dict]]:
    """Fetch live content from top RAG URLs + guessed ShareTechnote page."""
    urls: list[str] = []
    for c in rag_cites or []:
        u = c.get("url") or ""
        if u and (_SHARETECH.search(u) or _3GPP.search(u)) and u not in urls:
            urls.append(u)

    guess = guess_sharetechnote_url(query)
    if guess and guess not in urls:
        urls.insert(0, guess)

    parts: list[str] = []
    cites: list[dict] = []
    for url in urls[:1]:
        try:
            page = fetch_page_excerpt(url)
            if not page.get("ok"):
                continue
            parts.append(
                f"Live page: {page['title']} ({page['url']})\n{page['text']}"
            )
            cites.append(
                {
                    "title": page["title"],
                    "url": page["url"],
                    "source": "live_fetch",
                    "live": True,
                }
            )
        except Exception:
            continue

    return "\n\n---\n\n".join(parts), cites
