"""TelecomAI — LangGraph router over the TelecomDB knowledge layer."""

from __future__ import annotations

from .graph import build_graph, initial_state
from .loaders import TelecomDB


class TelecomAI:
    def __init__(self, db_path: str):
        self.db = TelecomDB(db_path)
        self.graph = build_graph(self.db)

    def run(self, query: str, history: list[dict[str, str]] | None = None) -> str:
        return self.run_with_trace(query, history=history)["answer"]

    def run_with_trace(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict:
        result = self.graph.invoke(initial_state(query, history))
        return {
            "answer": result.get("answer") or "",
            "intent": result.get("intent"),
            "steps": result.get("steps") or [],
        }
