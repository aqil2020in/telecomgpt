"""BM25 retrieval over ingested reference chunks."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from .store import DEFAULT_STORE, load_chunks

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class RagRetriever:
    def __init__(self, chunks: list[dict] | None = None) -> None:
        self.chunks = chunks if chunks is not None else load_chunks()
        self._df: Counter[str] = Counter()
        self._chunk_tokens: list[list[str]] = []
        self._avg_len = 0.0
        self._built = False

    def _build(self) -> None:
        if self._built:
            return
        for ch in self.chunks:
            tokens = _tokenize(ch.get("text", ""))
            self._chunk_tokens.append(tokens)
            for t in set(tokens):
                self._df[t] += 1
        n = len(self.chunks) or 1
        self._avg_len = sum(len(t) for t in self._chunk_tokens) / n
        self._built = True

    def search(self, query: str, *, k: int = 5) -> list[dict]:
        if not self.chunks:
            return []
        self._build()
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        n = len(self.chunks)
        scores: list[tuple[float, int]] = []
        k1, b = 1.5, 0.75
        for i, tokens in enumerate(self._chunk_tokens):
            if not tokens:
                continue
            tf = Counter(tokens)
            dl = len(tokens)
            score = 0.0
            for term in q_tokens:
                if term not in tf:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                freq = tf[term]
                denom = freq + k1 * (1 - b + b * dl / self._avg_len)
                score += idf * (freq * (k1 + 1)) / denom
            # Boost title/url term matches
            meta = (self.chunks[i].get("title", "") + " " + self.chunks[i].get("url", "")).lower()
            for term in q_tokens:
                if term in meta:
                    score += 0.5
            if score > 0:
                scores.append((score, i))
        scores.sort(reverse=True)
        return [{**self.chunks[i], "score": round(s, 3)} for s, i in scores[:k]]


def retrieve_context(query: str, *, k: int = 5, store_path: Path | None = None) -> str:
    retriever = RagRetriever(load_chunks(store_path))
    hits = retriever.search(query, k=k)
    if not hits:
        return ""
    parts = []
    for h in hits:
        parts.append(
            f"Source: {h.get('title', 'ref')} ({h.get('url', '')})\n{h.get('text', '')}"
        )
    return "\n\n---\n\n".join(parts)


def retrieve_with_citations(query: str, *, k: int = 5) -> tuple[str, list[dict]]:
    retriever = RagRetriever()
    hits = retriever.search(query, k=k)
    if not hits:
        return "", []
    parts = []
    for h in hits:
        parts.append(
            f"Source: {h.get('title', 'ref')} ({h.get('url', '')})\n{h.get('text', '')}"
        )
    context = "\n\n---\n\n".join(parts)
    cites = [{"title": h.get("title"), "url": h.get("url"), "score": h.get("score")} for h in hits]
    return context, cites
