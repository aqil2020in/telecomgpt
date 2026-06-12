"""Telecom-focused web search via Tavily API (optional)."""

from __future__ import annotations

import os
from typing import Any

TELECOM_DOMAINS = [
    "sharetechnote.com",
    "sqimway.com",
    "3gpp.org",
    "etsi.org",
    "gsma.com",
]


def tavily_search(query: str, *, max_results: int = 4) -> tuple[str, list[dict]]:
    """Search web with domain bias toward telecom references."""
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "", []

    try:
        import requests

        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": f"{query} 5G NR LTE 3GPP",
                "search_depth": "basic",
                "max_results": max_results,
                "include_domains": TELECOM_DOMAINS,
            },
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return "", []

    parts: list[str] = []
    cites: list[dict] = []
    for r in data.get("results") or []:
        title = r.get("title") or "Web result"
        url = r.get("url") or ""
        content = (r.get("content") or "")[:1200]
        if not content:
            continue
        parts.append(f"Web: {title} ({url})\n{content}")
        cites.append({"title": title, "url": url, "source": "tavily", "score": r.get("score")})

    return "\n\n---\n\n".join(parts), cites


def web_search_telecom(query: str) -> dict[str, Any]:
    """Unified web search entry — Tavily when configured."""
    context, cites = tavily_search(query)
    return {
        "ok": bool(context),
        "context": context,
        "citations": cites,
        "provider": "tavily" if os.environ.get("TAVILY_API_KEY") else "none",
    }
