"""Autonomous planning — decompose user goals into agent steps."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .loaders import TelecomDB

AgentName = str  # telecom_kb | research | analytics | presentation | synthesizer

_PPT_KW = (
    "powerpoint",
    "ppt",
    "presentation",
    "slides",
    "slide deck",
    "report",
    "generate report",
)
_ANALYTICS_KW = (
    "csv",
    "chart",
    "plot",
    "dashboard",
    "kaggle",
    "analyze data",
    "analyze the",
    "summarize the",
    "drive test",
    "kpi",
    "rsrp",
    "throughput trend",
    "log file",
    "qxdm",
    "dataset",
)
_RESEARCH_KW = (
    "3gpp",
    "specification",
    "sharetechnote",
    "reference",
    "how does",
    "explain",
    "what is",
    "compare",
    "difference",
    "versus",
    " vs ",
)
_DEVICE_KW = ("s23", "s24", "s25", "iphone", "pixel", "device")
_CA_KW = ("ca", "carrier aggregation", "endc", "nrdc")
_PHY_KW = ("arfcn", "gscn", "throughput", "mhz", "ghz", "ssb")


def create_plan(query: str, db: "TelecomDB | None" = None) -> dict:
    """Rule-based planner with optional LLM refinement."""
    q = query.lower().strip()
    steps: list[dict] = []
    agents: list[AgentName] = []

    wants_ppt = any(k in q for k in _PPT_KW)
    wants_analytics = any(k in q for k in _ANALYTICS_KW)
    wants_research = any(k in q for k in _RESEARCH_KW)
    wants_kb = any(k in q for k in _DEVICE_KW + _CA_KW + _PHY_KW) or (
        db and (db.glossary_lookup(query) or db.answer_comparison(query))
    )

    if wants_ppt:
        agents = ["research", "telecom_kb", "presentation", "synthesizer"]
        steps = [
            {"step": 1, "agent": "research", "action": "Gather reference material and specs"},
            {"step": 2, "agent": "telecom_kb", "action": "Pull KB facts, bands, and glossary"},
            {"step": 3, "agent": "presentation", "action": "Build PowerPoint slide deck"},
            {"step": 4, "agent": "synthesizer", "action": "Summarize and attach download link"},
        ]
    elif wants_analytics:
        agents = ["analytics", "research", "synthesizer"]
        steps = [
            {"step": 1, "agent": "analytics", "action": "Analyze CSV/log/Kaggle data"},
            {"step": 2, "agent": "research", "action": "Add telecom context for metrics"},
            {"step": 3, "agent": "synthesizer", "action": "Combine findings into answer"},
        ]
    elif wants_kb and not wants_research:
        agents = ["telecom_kb", "synthesizer"]
        steps = [
            {"step": 1, "agent": "telecom_kb", "action": "Answer from knowledge base and calculators"},
            {"step": 2, "agent": "synthesizer", "action": "Format final response"},
        ]
    elif wants_research or wants_kb:
        agents = ["telecom_kb", "research", "synthesizer"]
        steps = [
            {"step": 1, "agent": "telecom_kb", "action": "Check structured KB and comparisons"},
            {"step": 2, "agent": "research", "action": "Retrieve RAG + vector memory excerpts"},
            {"step": 3, "agent": "synthesizer", "action": "Synthesize grounded answer"},
        ]
    else:
        agents = ["research", "telecom_kb", "synthesizer"]
        steps = [
            {"step": 1, "agent": "research", "action": "Search references and past context"},
            {"step": 2, "agent": "telecom_kb", "action": "Supplement with KB if applicable"},
            {"step": 3, "agent": "synthesizer", "action": "Produce final answer"},
        ]

    return {
        "goal": query,
        "agents": agents,
        "steps": steps,
        "primary_agent": agents[0],
        "requires_tools": wants_analytics or wants_ppt or any(k in q for k in _PHY_KW),
        "requires_ppt": wants_ppt,
    }


def refine_plan_with_llm(query: str, base_plan: dict) -> dict:
    """Optional LLM plan refinement when OpenAI/Ollama is available."""
    from .reasoning import call_llm_json

    prompt = (
        f"User query: {query}\n\n"
        f"Draft plan: {json.dumps(base_plan, indent=2)}\n\n"
        "Return JSON with keys: agents (list), steps (list of {{step, agent, action}}), "
        "primary_agent, requires_tools (bool), requires_ppt (bool). "
        "Agents must be from: telecom_kb, research, analytics, presentation, synthesizer."
    )
    refined = call_llm_json(prompt)
    if not refined:
        return base_plan
    base_plan.update({k: refined[k] for k in refined if k in base_plan or k in refined})
    return base_plan


def parse_tool_calls(text: str) -> list[dict]:
    """Extract tool calls from LLM JSON block."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        match = re.search(r"(\{[^{}]*\"tool\"[^{}]*\})", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
        if isinstance(data, list):
            return data
        if "tools" in data:
            return data["tools"]
        if "tool" in data:
            return [data]
    except json.JSONDecodeError:
        pass
    return []
