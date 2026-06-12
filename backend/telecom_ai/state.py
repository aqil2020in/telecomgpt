"""Shared LangGraph state for TelecomGPT orchestration."""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, Literal, TypedDict

Intent = Literal[
    "device",
    "ca_endc",
    "phy_math",
    "band_glossary",
    "glossary",
    "band_regulatory",
    "llm",
]

AgentName = Literal[
    "telecom_kb",
    "research",
    "analytics",
    "presentation",
    "synthesizer",
]


class TelecomState(TypedDict, total=False):
    query: str
    intent: Intent | None
    answer: str | None
    context: str | None
    history: list[dict[str, str]]
    sources: list[dict]
    steps: Annotated[list[str], operator.add]


class OrchestratorState(TypedDict, total=False):
    query: str
    session_id: str
    history: list[dict[str, str]]
    plan: dict[str, Any]
    active_agent: str | None
    agent_index: int
    agent_outputs: list[dict[str, Any]]
    memory_context: str | None
    answer: str | None
    sources: list[dict]
    artifacts: list[dict]
    confidence: float | None
    needs_clarification: bool
    steps: Annotated[list[str], operator.add]


ChatMessage = dict[str, Any]


def initial_orchestrator_state(
    query: str,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
) -> OrchestratorState:
    return {
        "query": query,
        "session_id": session_id or str(uuid.uuid4())[:12],
        "history": history or [],
        "plan": {},
        "active_agent": None,
        "agent_index": 0,
        "agent_outputs": [],
        "memory_context": None,
        "answer": None,
        "sources": [],
        "artifacts": [],
        "confidence": None,
        "needs_clarification": False,
        "steps": [],
    }
