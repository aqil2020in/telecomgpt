"""TelecomAI — multi-agent orchestrator over TelecomDB knowledge layer."""

from __future__ import annotations

import os

from .graph import build_graph, initial_state as legacy_initial_state
from .loaders import TelecomDB
from .orchestrator import build_orchestrator_graph, initial_state as orch_initial_state


class TelecomAI:
    def __init__(self, db_path: str):
        self.db = TelecomDB(db_path)
        self._use_orchestrator = os.environ.get("TELECOMGPT_MODE", "orchestrator") != "legacy"
        self.graph = (
            build_orchestrator_graph(self.db)
            if self._use_orchestrator
            else build_graph(self.db)
        )

    def run(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        session_id: str | None = None,
    ) -> str:
        return self.run_with_trace(query, history=history, session_id=session_id)["answer"]

    def run_with_trace(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        session_id: str | None = None,
    ) -> dict:
        if self._use_orchestrator:
            state = orch_initial_state(query, history, session_id)
            result = self.graph.invoke(state)
            return {
                "answer": result.get("answer") or "",
                "session_id": result.get("session_id"),
                "plan": result.get("plan"),
                "active_agent": result.get("active_agent"),
                "steps": result.get("steps") or [],
                "sources": result.get("sources") or [],
                "artifacts": result.get("artifacts") or [],
                "confidence": result.get("confidence"),
                "needs_clarification": result.get("needs_clarification"),
                "workflow_tasks": result.get("workflow_tasks") or [],
                "guardrail_issues": result.get("guardrail_issues") or [],
                "memory_context": result.get("memory_context"),
                "mode": "orchestrator",
            }
        result = self.graph.invoke(legacy_initial_state(query, history))
        return {
            "answer": result.get("answer") or "",
            "intent": result.get("intent"),
            "steps": result.get("steps") or [],
            "sources": result.get("sources") or [],
            "mode": "legacy",
        }

    def list_tools(self) -> list[dict]:
        from .tools import build_tool_registry

        return build_tool_registry(self.db).list_specs()
