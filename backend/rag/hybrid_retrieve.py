"""Hybrid retrieval — BM25 + vector memory, merged and deduplicated."""

from __future__ import annotations

from .retrieve import retrieve_with_citations


def hybrid_retrieve(
    query: str,
    *,
    k: int = 5,
    session_id: str | None = None,
) -> tuple[str, list[dict]]:
    bm25_context, bm25_cites = retrieve_with_citations(query, k=k)
    vector_cites: list[dict] = []
    vector_parts: list[str] = []

    try:
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

    seen_urls = {c.get("url") for c in bm25_cites}
    merged_cites = list(bm25_cites)
    for c in vector_cites:
        if c.get("url") and c["url"] not in seen_urls:
            merged_cites.append(c)
            seen_urls.add(c["url"])

    parts = []
    if bm25_context:
        parts.append(bm25_context)
    if vector_parts:
        parts.append("Vector memory excerpts:\n" + "\n---\n".join(vector_parts[:3]))

    return "\n\n---\n\n".join(parts), merged_cites[: k + 2]
