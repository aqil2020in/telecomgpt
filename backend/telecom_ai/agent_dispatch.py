"""Dispatch table for all orchestrator agents."""

from __future__ import annotations

from typing import Any, Callable

from .agents.test_engineer import (
    run_bts_config_agent,
    run_fault_analysis_agent,
    run_feature_validation_agent,
    run_log_debug_agent,
    run_rf_metrics_agent,
)
from .agents.extended import (
    run_comparison_agent,
    run_compliance_agent,
    run_coverage_optimizer_agent,
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
    "telecom_kb", "research", "analytics", "drive_test", "rf_metrics", "coverage_optimizer", "log", "log_debug",
    "fault_analysis", "feature_validation", "bts_config",
    "prediction", "compliance", "spec", "comparison", "react", "autogen", "crew",
    "deploy", "eval",
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
    memory_context: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict:
    from .agents.taxonomy import agent_category

    meta = {"category": agent_category(name)}
    if name == "telecom_kb":
        out = run_telecom_kb_agent(query, db, tools)
    elif name == "research":
        out = run_research_agent(query, tools, session_id=session_id)
    elif name == "analytics":
        out = run_analytics_agent(query, tools)
    elif name == "drive_test":
        out = run_drive_test_agent(query, tools, session_id=session_id)
    elif name == "rf_metrics":
        out = run_rf_metrics_agent(query, tools, session_id=session_id)
    elif name == "coverage_optimizer":
        out = run_coverage_optimizer_agent(query, tools, session_id=session_id)
    elif name == "log":
        out = run_log_debug_agent(query, tools, session_id=session_id)
    elif name == "log_debug":
        out = run_log_debug_agent(query, tools, session_id=session_id)
    elif name == "fault_analysis":
        out = run_fault_analysis_agent(query, tools, session_id=session_id)
    elif name == "feature_validation":
        out = run_feature_validation_agent(query, db, tools)
    elif name == "bts_config":
        out = run_bts_config_agent(query, tools, session_id=session_id)
    elif name == "prediction":
        out = run_prediction_agent(query, tools)
    elif name == "compliance":
        out = run_compliance_agent(query, db, tools)
    elif name == "spec":
        out = run_spec_agent(query, tools, session_id=session_id)
    elif name == "comparison":
        out = run_comparison_agent(query, db, tools)
    elif name == "presentation":
        combined = "\n\n".join(o.get("content", "") for o in (agent_outputs or []) if o.get("content"))
        out = run_presentation_agent(query, combined or query, tools, session_id=session_id)
    elif name == "verifier":
        out = run_verifier_agent(query, answer or "", agent_outputs or [], db)
    elif name == "deploy":
        out = run_deploy_agent()
    elif name == "eval":
        out = run_eval_agent(db)
    elif name == "react":
        from .react_loop import run_react_tools
        out = run_react_tools(query, tools.list_specs(), tools)
    elif name == "autogen":
        from .engines.autogen_runner import run_autogen_tools
        out = run_autogen_tools(
            query,
            tools.list_specs(),
            tools,
            memory_context=memory_context,
        )
    elif name == "crew":
        from .engines.crew_runner import run_telecom_crew
        out = run_telecom_crew(
            query,
            tools,
            db,
            session_id=session_id,
            memory_context=memory_context,
        )
    elif name == "synthesizer":
        out = run_synthesizer(
            query,
            agent_outputs or [],
            db,
            history=history,
            memory_context=memory_context,
        )
    else:
        out = {"agent": name, "content": ""}
    out.update(meta)
    return out


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
