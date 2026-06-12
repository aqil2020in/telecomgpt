"""Memory backend adapters — Chroma (default), Mem0, LangMem, Letta."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class MemoryAdapter(ABC):
    """Pluggable long-term memory backend (Mem0, LangMem, Letta, etc.)."""

    name: str = "base"

    @abstractmethod
    def add(self, text: str, *, user_id: str, metadata: dict | None = None) -> str:
        ...

    @abstractmethod
    def search(self, query: str, *, user_id: str, limit: int = 5) -> list[dict]:
        ...

    @abstractmethod
    def refresh(self, *, user_id: str) -> dict:
        ...


class ChromaAdapter(MemoryAdapter):
    """Default adapter — uses in-repo VectorMemory + MemoryManager."""

    name = "chroma"

    def __init__(self) -> None:
        from .memory_manager import MemoryManager

        self._mgr_cls = MemoryManager

    def add(self, text: str, *, user_id: str, metadata: dict | None = None) -> str:
        kind = (metadata or {}).get("kind", "episodic")
        return self._mgr_cls(user_id).store(text, kind=kind, metadata=metadata)

    def search(self, query: str, *, user_id: str, limit: int = 5) -> list[dict]:
        return self._mgr_cls(user_id).retrieve(query, k=limit)

    def refresh(self, *, user_id: str) -> dict:
        return self._mgr_cls(user_id).refresh()


class Mem0Adapter(MemoryAdapter):
    """Mem0 (mem0ai) — https://github.com/mem0ai/mem0"""

    name = "mem0"

    def __init__(self) -> None:
        self._client = None
        try:
            from mem0 import Memory  # type: ignore

            self._client = Memory()
        except ImportError:
            pass

    def add(self, text: str, *, user_id: str, metadata: dict | None = None) -> str:
        if not self._client:
            return ChromaAdapter().add(text, user_id=user_id, metadata=metadata)
        result = self._client.add(text, user_id=user_id, metadata=metadata or {})
        return str(result)

    def search(self, query: str, *, user_id: str, limit: int = 5) -> list[dict]:
        if not self._client:
            return ChromaAdapter().search(query, user_id=user_id, limit=limit)
        hits = self._client.search(query, user_id=user_id, limit=limit)
        return [{"text": h.get("memory", ""), "metadata": h.get("metadata", {}), "score": h.get("score")} for h in hits]

    def refresh(self, *, user_id: str) -> dict:
        return ChromaAdapter().refresh(user_id=user_id)


class LangMemAdapter(MemoryAdapter):
    """LangMem-style adapter — uses LangGraph store when available, else Chroma."""

    name = "langmem"

    def add(self, text: str, *, user_id: str, metadata: dict | None = None) -> str:
        return ChromaAdapter().add(text, user_id=user_id, metadata=metadata)

    def search(self, query: str, *, user_id: str, limit: int = 5) -> list[dict]:
        return ChromaAdapter().search(query, user_id=user_id, limit=limit)

    def refresh(self, *, user_id: str) -> dict:
        return ChromaAdapter().refresh(user_id=user_id)


class LettaAdapter(MemoryAdapter):
    """Letta (formerly MemGPT) — REST API stub; set LETTA_API_URL + LETTA_API_KEY."""

    name = "letta"

    def __init__(self) -> None:
        self.base_url = os.environ.get("LETTA_API_URL", "").rstrip("/")
        self.api_key = os.environ.get("LETTA_API_KEY", "")

    def add(self, text: str, *, user_id: str, metadata: dict | None = None) -> str:
        if not self.base_url:
            return ChromaAdapter().add(text, user_id=user_id, metadata=metadata)
        try:
            import requests

            resp = requests.post(
                f"{self.base_url}/v1/agents/{user_id}/memory",
                json={"text": text, "metadata": metadata or {}},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("id", "ok")
        except Exception:
            return ChromaAdapter().add(text, user_id=user_id, metadata=metadata)

    def search(self, query: str, *, user_id: str, limit: int = 5) -> list[dict]:
        if not self.base_url:
            return ChromaAdapter().search(query, user_id=user_id, limit=limit)
        try:
            import requests

            resp = requests.get(
                f"{self.base_url}/v1/agents/{user_id}/memory/search",
                params={"query": query, "limit": limit},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception:
            return ChromaAdapter().search(query, user_id=user_id, limit=limit)

    def refresh(self, *, user_id: str) -> dict:
        return ChromaAdapter().refresh(user_id=user_id)


def get_memory_adapter(provider: str | None = None) -> MemoryAdapter:
    name = (provider or os.environ.get("TELECOMGPT_MEMORY", "chroma")).strip().lower()
    adapters: dict[str, type[MemoryAdapter]] = {
        "chroma": ChromaAdapter,
        "mem0": Mem0Adapter,
        "langmem": LangMemAdapter,
        "letta": LettaAdapter,
    }
    cls = adapters.get(name, ChromaAdapter)
    return cls()
