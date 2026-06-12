"""Dispatch table for all orchestrator agents."""

from __future__ import annotations

from typing import Any, Callable

from .agents.extended import (
    run_comparison_agent,
    run_compliance_agent,
    run_deploy_agent,
    run_drive_test_agent,
    run_eval_agent,
    run_log_agent,
    run_prediction_agent,
    run_spec_agent,
    run_verifier_agent,
)
from .agents.specialists import (
    run_analytics_agent,
    run_presentation_agent,
    run_research_agent,
    run_synthesizer,
    run_telecom_kb_agent,
)
from .loaders import TelecomDB
from .tools import ToolRegistry

# Agents that run in parallel batch (not sequential loop)
PARALLEL_AGENTS = frozenset({
    "telecom_kb", "research", "analytics", "drive_test", "log",
    "prediction", "compliance", "spec", "comparison", "react", "deploy", "eval",
})

SEQUENTIAL_AGENTS = frozenset({"presentation", "synthesizer", "verifier"})


def run_agent(
    name: str,
    query: str,
    db: TelecomDB,
    tools: ToolRegistry,
    session_id: str = "default",
    *,
    agent_outputs: list[dict] | None = None,
    answer: str | None = None,
) -> dict:
    if name == "telecom_kb":
        return run_telecom_kb_agent(query, db, tools)
    if name == "research":
        return run_research_agent(query, tools, session_id=session_id)
    if name == "analytics":
        return run_analytics_agent(query, tools)
    if name == "drive_test":
        return run_drive_test_agent(query, tools, session_id=session_id)
    if name == "log":
        return run_log_agent(query, tools, session_id=session_id)
    if name == "prediction":
        return run_prediction_agent(query, tools)
    if name == "compliance":
        return run_compliance_agent(query, db, tools)
    if name == "spec":
        return run_spec_agent(query, tools, session_id=session_id)
    if name == "comparison":
        return run_comparison_agent(query, db, tools)
    if name == "presentation":
        combined = "\n\n".join(o.get("content", "") for o in (agent_outputs or []) if o.get("content"))
        return run_presentation_agent(query, combined or query, tools, session_id=session_id)
    if name == "verifier":
        return run_verifier_agent(query, answer or "", agent_outputs or [], db)
    if name == "deploy":
        return run_deploy_agent()
    if name == "eval":
        return run_eval_agent(db)
    if name == "react":
        from .react_loop import run_react_tools
        return run_react_tools(query, tools.list_specs(), tools)
    if name == "synthesizer":
        return run_synthesizer(query, agent_outputs or [], db)
    return {"agent": name, "content": ""}


def merge_agent_result(state: dict, out: dict) -> dict:
    """Merge single agent output into orchestrator state fields."""
    outputs = list(state.get("agent_outputs") or [])
    outputs.append(out)
    artifacts = list(state.get("artifacts") or [])
    artifacts.extend(out.get("artifacts") or [])
    if out.get("artifact"):
        artifacts.append(out["artifact"])
    sources = list(state.get("sources") or [])
    sources.extend(out.get("sources") or [])
    steps = [f"agent:{out.get('agent', '?')}"]
    return {
        "agent_outputs": outputs,
        "artifacts": artifacts,
        "sources": sources,
        "steps": steps,
    }
