"""Multi-agent orchestrator graph — supervisor, planning, tools, memory."""

from __future__ import annotations

import os

from langgraph.graph import END, START, StateGraph

from .agents.specialists import (
    run_analytics_agent,
    run_presentation_agent,
    run_research_agent,
    run_synthesizer,
    run_telecom_kb_agent,
)
from .loaders import TelecomDB
from .planning import create_plan, refine_plan_with_llm
from .state import OrchestratorState, initial_orchestrator_state
from .tools import ToolRegistry, build_tool_registry


def build_orchestrator_graph(db: TelecomDB):
    graph = StateGraph(OrchestratorState)
    tools = build_tool_registry(db)

    def load_memory(state: OrchestratorState) -> dict:
        from memory.session_memory import SessionMemory
        from memory.vector_store import VectorMemory

        sid = state.get("session_id") or "default"
        session = SessionMemory(sid)
        mem = VectorMemory()
        recalled = mem.search(state["query"], k=3, session_id=sid)
        ctx = session.summary_context()
        mem_lines = "\n".join(f"- {r.get('text', '')[:200]}" for r in recalled)
        return {
            "memory_context": f"{ctx}\n\nRecalled:\n{mem_lines}".strip(),
            "steps": ["memory:loaded"],
        }

    def plan(state: OrchestratorState) -> dict:
        base = create_plan(state["query"], db)
        if os.environ.get("TELECOMGPT_LLM_PLAN", "1") == "1":
            base = refine_plan_with_llm(state["query"], base)
        return {
            "plan": base,
            "active_agent": base.get("primary_agent"),
            "steps": [f"plan:{len(base.get('steps', []))}_steps"],
        }

    def orchestrator(state: OrchestratorState) -> dict:
        plan_data = state.get("plan") or {}
        agents = plan_data.get("agents") or ["research", "telecom_kb", "synthesizer"]
        idx = state.get("agent_index") or 0
        if idx >= len(agents):
            return {"active_agent": "synthesizer", "steps": ["orchestrator:done"]}
        return {
            "active_agent": agents[idx],
            "agent_index": idx,
            "steps": [f"orchestrator:dispatch->{agents[idx]}"],
        }

    def telecom_kb_node(state: OrchestratorState) -> dict:
        out = run_telecom_kb_agent(state["query"], db, tools)
        outputs = list(state.get("agent_outputs") or [])
        outputs.append(out)
        return {
            "agent_outputs": outputs,
            "agent_index": (state.get("agent_index") or 0) + 1,
            "steps": ["agent:telecom_kb"],
        }

    def research_node(state: OrchestratorState) -> dict:
        out = run_research_agent(
            state["query"],
            tools,
            session_id=state.get("session_id") or "default",
        )
        outputs = list(state.get("agent_outputs") or [])
        outputs.append(out)
        sources = list(state.get("sources") or [])
        sources.extend(out.get("sources") or [])
        return {
            "agent_outputs": outputs,
            "sources": sources,
            "agent_index": (state.get("agent_index") or 0) + 1,
            "steps": ["agent:research"],
        }

    def analytics_node(state: OrchestratorState) -> dict:
        out = run_analytics_agent(state["query"], tools)
        outputs = list(state.get("agent_outputs") or [])
        outputs.append(out)
        artifacts = list(state.get("artifacts") or [])
        artifacts.extend(out.get("artifacts") or [])
        return {
            "agent_outputs": outputs,
            "artifacts": artifacts,
            "agent_index": (state.get("agent_index") or 0) + 1,
            "steps": ["agent:analytics"],
        }

    def presentation_node(state: OrchestratorState) -> dict:
        combined = "\n\n".join(
            o.get("content", "") for o in (state.get("agent_outputs") or []) if o.get("content")
        )
        out = run_presentation_agent(
            state["query"],
            combined or state["query"],
            tools,
            session_id=state.get("session_id") or "default",
        )
        outputs = list(state.get("agent_outputs") or [])
        outputs.append(out)
        artifacts = list(state.get("artifacts") or [])
        if out.get("artifact"):
            artifacts.append(out["artifact"])
        return {
            "agent_outputs": outputs,
            "artifacts": artifacts,
            "agent_index": (state.get("agent_index") or 0) + 1,
            "steps": ["agent:presentation"],
        }

    def synthesizer_node(state: OrchestratorState) -> dict:
        out = run_synthesizer(
            state["query"],
            state.get("agent_outputs") or [],
            db,
            history=state.get("history"),
        )
        artifacts = list(state.get("artifacts") or [])
        artifacts.extend(out.get("artifacts") or [])
        sources = list(state.get("sources") or [])
        sources.extend(out.get("sources") or [])
        return {
            "answer": out.get("content") or "",
            "artifacts": artifacts,
            "sources": sources,
            "agent_index": 999,
            "steps": ["agent:synthesizer"],
        }

    def save_memory(state: OrchestratorState) -> dict:
        from memory.session_memory import SessionMemory
        from memory.vector_store import VectorMemory

        sid = state.get("session_id") or "default"
        SessionMemory(sid).save_turn("user", state["query"])
        answer = state.get("answer") or ""
        if answer:
            SessionMemory(sid).save_turn("assistant", answer[:4000])
            VectorMemory().remember(
                f"Q: {state['query'][:500]}\nA: {answer[:1500]}",
                session_id=sid,
                kind="conversation",
            )
        return {"steps": ["memory:saved"]}

    def route_agent(state: OrchestratorState) -> str:
        agent = state.get("active_agent") or "synthesizer"
        idx = state.get("agent_index") or 0
        plan_data = state.get("plan") or {}
        agents = plan_data.get("agents") or []
        if idx >= len(agents) or agent == "synthesizer" or idx >= 998:
            return "synthesizer"
        mapping = {
            "telecom_kb": "telecom_kb",
            "research": "research",
            "analytics": "analytics",
            "presentation": "presentation",
            "synthesizer": "synthesizer",
        }
        return mapping.get(agent, "research")

    def after_agent(state: OrchestratorState) -> str:
        idx = state.get("agent_index") or 0
        plan_data = state.get("plan") or {}
        agents = plan_data.get("agents") or []
        if idx >= len(agents):
            return "synthesizer"
        return "orchestrator"

    graph.add_node("load_memory", load_memory)
    graph.add_node("plan", plan)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("telecom_kb", telecom_kb_node)
    graph.add_node("research", research_node)
    graph.add_node("analytics", analytics_node)
    graph.add_node("presentation", presentation_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("save_memory", save_memory)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "plan")
    graph.add_edge("plan", "orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_agent,
        {
            "telecom_kb": "telecom_kb",
            "research": "research",
            "analytics": "analytics",
            "presentation": "presentation",
            "synthesizer": "synthesizer",
        },
    )

    for node in ("telecom_kb", "research", "analytics", "presentation"):
        graph.add_conditional_edges(
            node,
            after_agent,
            {"orchestrator": "orchestrator", "synthesizer": "synthesizer"},
        )

    graph.add_edge("synthesizer", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile()


def initial_state(
    query: str,
    history: list[dict[str, str]] | None = None,
    session_id: str = "default",
) -> OrchestratorState:
    return initial_orchestrator_state(query, history, session_id)
