"""ChromaDB RAG layer — troubleshooting guides and playbooks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tnic.config import get_settings
from tnic.logging_config import get_logger

log = get_logger(__name__)


class RAGStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._collection = None
        self._fallback_docs: list[dict[str, str]] = []

    def _init_chroma(self):
        if self._collection is not None:
            return
        if not self.settings.enable_chroma:
            return
        try:
            import chromadb

            path = Path(self.settings.chroma_persist_dir)
            path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(path))
            self._collection = client.get_or_create_collection(
                name=self.settings.rag_collection,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            log.warning("ChromaDB unavailable: %s", e)
            self._collection = None

    def load_seed_documents(self) -> int:
        guides_path = self.settings.data_dir / "knowledge" / "troubleshooting_guides.json"
        if not guides_path.exists():
            return 0
        data = json.loads(guides_path.read_text(encoding="utf-8"))
        docs = data.get("documents") or []
        self._fallback_docs = docs
        self._init_chroma()
        if not self._collection:
            return len(docs)
        ids, texts, metas = [], [], []
        for i, doc in enumerate(docs):
            ids.append(doc.get("id") or f"doc_{i}")
            texts.append(doc.get("text", ""))
            metas.append({"title": doc.get("title", ""), "category": doc.get("category", "")})
        if ids:
            try:
                self._collection.upsert(ids=ids, documents=texts, metadatas=metas)
            except Exception as e:
                log.warning("Chroma upsert failed: %s", e)
        return len(docs)

    def search(self, query: str, k: int = 5) -> list[dict[str, str]]:
        self._init_chroma()
        if self._collection:
            try:
                res = self._collection.query(query_texts=[query], n_results=min(k, 10))
                out = []
                for i, doc in enumerate(res.get("documents", [[]])[0]):
                    meta = (res.get("metadatas") or [[]])[0][i] if res.get("metadatas") else {}
                    out.append({
                        "title": meta.get("title", ""),
                        "category": meta.get("category", ""),
                        "text": doc[:800],
                    })
                if out:
                    return out
            except Exception as e:
                log.warning("Chroma query failed: %s", e)

        # BM25-like fallback: token overlap
        q_tokens = set(query.lower().split())
        scored: list[tuple[int, dict]] = []
        for doc in self._fallback_docs:
            text = doc.get("text", "").lower()
            score = sum(1 for t in q_tokens if t in text)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"title": d.get("title", ""), "category": d.get("category", ""), "text": d.get("text", "")[:800]}
            for _, d in scored[:k]
        ]


_rag: RAGStore | None = None


def get_rag_store() -> RAGStore:
    global _rag
    if _rag is None:
        _rag = RAGStore()
        _rag.load_seed_documents()
    return _rag
