"""Hybrid retrieval — BM25 + vector + live fetch + optional web search."""

from __future__ import annotations

import os

from .live_fetch import fetch_live_for_query
from .retrieve import retrieve_with_citations
from .web_search import tavily_search


def hybrid_retrieve(
    query: str,
    *,
    k: int = 5,
    session_id: str | None = None,
    live: bool | None = None,
    web: bool | None = None,
) -> tuple[str, list[dict]]:
    bm25_context, bm25_cites = retrieve_with_citations(query, k=k)
    vector_cites: list[dict] = []
    vector_parts: list[str] = []

    try:
        from memory.runtime_config import vector_enabled

        if not vector_enabled():
            return bm25_context, bm25_cites
        from memory.vector_store import VectorMemory

        hits = VectorMemory().search(query, k=k, session_id=session_id)
        for h in hits:
            if h.get("metadata", {}).get("kind") == "reference" or h.get("metadata", {}).get("url"):
                vector_cites.append(
                    {
                        "title": h.get("metadata", {}).get("title", "memory"),
                        "url": h.get("metadata", {}).get("url", ""),
                        "score": h.get("score"),
                        "source": "vector",
                    }
                )
            vector_parts.append(h.get("text", "")[:800])
    except Exception:
        pass

    merged_cites = list(bm25_cites)
    seen_urls = {c.get("url") for c in merged_cites if c.get("url")}

    for c in vector_cites:
        if c.get("url") and c["url"] not in seen_urls:
            merged_cites.append(c)
            seen_urls.add(c["url"])

    do_live = live if live is not None else os.environ.get("TELECOMGPT_LIVE_FETCH", "1") == "1"
    do_web = web if web is not None else os.environ.get("TELECOMGPT_WEB_SEARCH", "1") == "1"

    live_context, live_cites = ("", [])
    if do_live:
        try:
            live_context, live_cites = fetch_live_for_query(query, merged_cites)
            for c in live_cites:
                if c.get("url") and c["url"] not in seen_urls:
                    merged_cites.insert(0, c)
                    seen_urls.add(c["url"])
        except Exception:
            pass

    web_context, web_cites = ("", [])
    if do_web and os.environ.get("TAVILY_API_KEY"):
        try:
            web_context, web_cites = tavily_search(query, max_results=3)
            for c in web_cites:
                if c.get("url") and c["url"] not in seen_urls:
                    merged_cites.append(c)
                    seen_urls.add(c["url"])
        except Exception:
            pass

    parts = []
    if live_context:
        parts.append(f"Live reference fetch:\n{live_context}")
    if bm25_context:
        parts.append(bm25_context)
    if web_context:
        parts.append(f"Web search (telecom domains):\n{web_context}")
    if vector_parts:
        parts.append("Vector memory excerpts:\n" + "\n---\n".join(vector_parts[:3]))

    return "\n\n---\n\n".join(parts), merged_cites[: k + 4]
