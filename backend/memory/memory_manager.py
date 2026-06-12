"""Unified memory manager — short/long-term, semantic, episodic, procedural."""

from __future__ import annotations

import re
from typing import Any

from .session_memory import SessionMemory
from .user_profile import UserProfile
from .vector_store import VectorMemory

# Memory taxonomy (cognitive + operational)
MEMORY_KINDS = frozenset({"semantic", "episodic", "procedural", "conversation", "reference"})

_BAND_RE = re.compile(r"\bn(\d{1,3})\b", re.I)
_DEVICE_HINTS = ("s23", "s24", "s25", "iphone", "pixel")


class MemoryManager:
    """Orchestrates short-term session memory and long-term vector memory."""

    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self.session = SessionMemory(session_id)
        self.profile = UserProfile(session_id)
        self.vector = VectorMemory()

    # --- Short-term (working memory) ---

    def short_term_context(self, *, max_turns: int = 10) -> str:
        return self.session.summary_context(max_turns=max_turns)

    # --- Long-term retrieval by kind ---

    def retrieve(
        self,
        query: str,
        *,
        kinds: list[str] | None = None,
        k: int = 5,
    ) -> list[dict]:
        hits = self.vector.search(query, k=k * 2, session_id=self.session_id)
        if kinds:
            allowed = set(kinds)
            hits = [h for h in hits if h.get("metadata", {}).get("kind") in allowed]
        return hits[:k]

    def retrieve_semantic(self, query: str, k: int = 4) -> list[dict]:
        return self.retrieve(query, kinds=["semantic", "reference"], k=k)

    def retrieve_episodic(self, query: str, k: int = 4) -> list[dict]:
        return self.retrieve(query, kinds=["episodic", "conversation"], k=k)

    def retrieve_procedural(self, query: str, k: int = 3) -> list[dict]:
        return self.retrieve(query, kinds=["procedural"], k=k)

    # --- Store ---

    def store(
        self,
        text: str,
        *,
        kind: str = "episodic",
        metadata: dict | None = None,
    ) -> str:
        if kind not in MEMORY_KINDS:
            kind = "episodic"
        return self.vector.remember(
            text,
            session_id=self.session_id,
            kind=kind,
            metadata=metadata,
        )

    def store_semantic_fact(self, fact: str, *, source: str = "user") -> str:
        return self.store(f"Fact: {fact}", kind="semantic", metadata={"source": source})

    def store_procedure(self, name: str, steps: str) -> str:
        return self.store(
            f"Procedure '{name}':\n{steps}",
            kind="procedural",
            metadata={"procedure": name},
        )

    def persist_turn(self, role: str, content: str) -> None:
        self.session.save_turn(role, content)
        if role == "user":
            self.profile.update_from_query(content)
            self._extract_semantic_from_query(content)

    def persist_exchange(self, query: str, answer: str) -> None:
        self.persist_turn("user", query)
        self.persist_turn("assistant", answer[:4000])
        self.store(
            f"Q: {query[:500]}\nA: {answer[:1500]}",
            kind="episodic",
            metadata={"type": "qa_exchange"},
        )

    # --- Refresh / compaction ---

    def refresh(self) -> dict[str, Any]:
        """Compact session into long-term memory and extract semantic facts."""
        turns = self.session.load()
        if len(turns) < 8:
            return {"refreshed": False, "reason": "too_few_turns", "turns": len(turns)}

        summary_lines = []
        for t in turns[-20:]:
            summary_lines.append(f"{t['role']}: {t['content'][:200]}")
        summary = "Session summary:\n" + "\n".join(summary_lines)
        doc_id = self.store(summary, kind="episodic", metadata={"type": "session_summary"})

        extracted = 0
        for t in turns:
            if t["role"] != "user":
                continue
            for m in _BAND_RE.finditer(t["content"]):
                self.store_semantic_fact(f"User interested in band n{m.group(1)}", source="refresh")
                extracted += 1

        return {
            "refreshed": True,
            "summary_id": doc_id,
            "semantic_facts": extracted,
            "turns_compacted": len(turns),
        }

    # --- Assemble context for agents ---

    def assemble_context(self, query: str) -> str:
        parts: list[str] = []

        st = self.short_term_context()
        if st:
            parts.append(st)

        profile_line = self.profile.context_line()
        if profile_line:
            parts.append(profile_line)

        for label, hits in (
            ("Semantic memory", self.retrieve_semantic(query)),
            ("Episodic memory", self.retrieve_episodic(query)),
            ("Procedural memory", self.retrieve_procedural(query)),
        ):
            if hits:
                lines = [f"- {h.get('text', '')[:220]}" for h in hits[:3]]
                parts.append(f"{label}:\n" + "\n".join(lines))

        return "\n\n".join(parts).strip()

    def _extract_semantic_from_query(self, query: str) -> None:
        ql = query.lower()
        for m in _BAND_RE.finditer(query):
            self.store_semantic_fact(f"User mentioned band n{m.group(1)}", source="query")
        for dev in _DEVICE_HINTS:
            if dev in ql:
                self.store_semantic_fact(f"User mentioned device {dev}", source="query")
