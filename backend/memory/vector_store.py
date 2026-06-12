"""Vector memory store — ChromaDB with BM25 fallback."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "memory" / "vector"


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class _SimpleVectorIndex:
    """Lightweight in-process index when ChromaDB is unavailable."""

    def __init__(self) -> None:
        self.docs: list[dict] = []

    def add(self, doc_id: str, text: str, metadata: dict) -> None:
        self.docs.append({"id": doc_id, "text": text, "metadata": metadata, "tokens": _tokenize(text)})

    def search(self, query: str, k: int = 5, session_id: str | None = None) -> list[dict]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scores: list[tuple[float, dict]] = []
        for doc in self.docs:
            if session_id and doc["metadata"].get("session_id") not in (session_id, None, ""):
                continue
            tf = Counter(doc["tokens"])
            score = sum(tf.get(t, 0) for t in q_tokens) / (len(doc["tokens"]) or 1)
            if score > 0:
                scores.append((score, doc))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": d["id"],
                "text": d["text"],
                "metadata": d["metadata"],
                "score": round(s, 4),
            }
            for s, d in scores[:k]
        ]


class VectorMemory:
    def __init__(self, persist_dir: Path | None = None) -> None:
        self.persist_dir = persist_dir or _DEFAULT_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._fallback = _SimpleVectorIndex()
        self._fallback_path = self.persist_dir / "fallback_index.json"
        self._chroma = None
        self._collection = None
        self._load_fallback()
        self._init_chroma()

    def _init_chroma(self) -> None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.persist_dir / "chroma"))
            self._collection = client.get_or_create_collection(
                name="telecomgpt_memory",
                metadata={"hnsw:space": "cosine"},
            )
            self._chroma = client
        except Exception:
            self._chroma = None
            self._collection = None

    def _load_fallback(self) -> None:
        if not self._fallback_path.exists():
            return
        try:
            data = json.loads(self._fallback_path.read_text(encoding="utf-8"))
            for item in data:
                self._fallback.add(item["id"], item["text"], item.get("metadata", {}))
        except (json.JSONDecodeError, KeyError):
            pass

    def _save_fallback(self) -> None:
        payload = [
            {"id": d["id"], "text": d["text"], "metadata": d["metadata"]}
            for d in self._fallback.docs
        ]
        self._fallback_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def remember(
        self,
        text: str,
        *,
        session_id: str = "default",
        kind: str = "conversation",
        metadata: dict | None = None,
    ) -> str:
        doc_id = hashlib.sha256(f"{session_id}:{text[:200]}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:16]
        meta = {"session_id": session_id, "kind": kind, "ts": datetime.now(timezone.utc).isoformat(), **(metadata or {})}

        if self._collection is not None:
            try:
                self._collection.add(ids=[doc_id], documents=[text], metadatas=[meta])
            except Exception:
                self._fallback.add(doc_id, text, meta)
                self._save_fallback()
        else:
            self._fallback.add(doc_id, text, meta)
            self._save_fallback()
        return doc_id

    def search(self, query: str, *, k: int = 5, session_id: str | None = None) -> list[dict]:
        if self._collection is not None:
            try:
                where = {"session_id": session_id} if session_id else None
                result = self._collection.query(
                    query_texts=[query],
                    n_results=k,
                    where=where,
                )
                docs = result.get("documents", [[]])[0]
                metas = result.get("metadatas", [[]])[0]
                ids = result.get("ids", [[]])[0]
                dists = result.get("distances", [[]])[0]
                return [
                    {
                        "id": ids[i],
                        "text": docs[i],
                        "metadata": metas[i] if i < len(metas) else {},
                        "score": round(1 - (dists[i] if i < len(dists) else 0), 4),
                    }
                    for i in range(len(docs))
                ]
            except Exception:
                pass
        return self._fallback.search(query, k=k, session_id=session_id)

    def ingest_rag_chunks(self, chunks: list[dict], *, batch_size: int = 100) -> int:
        """Index RAG chunks into vector memory for hybrid retrieval."""
        count = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            for ch in batch:
                text = ch.get("text", "")
                if not text.strip():
                    continue
                self.remember(
                    text[:2000],
                    session_id="rag",
                    kind="reference",
                    metadata={"url": ch.get("url"), "title": ch.get("title")},
                )
                count += 1
        return count
