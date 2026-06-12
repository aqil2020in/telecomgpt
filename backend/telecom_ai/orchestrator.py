"""Multi-agent orchestrator graph — planning, parallel agents, verifier, memory."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import END, START, StateGraph

from .agent_dispatch import merge_agent_result, run_agent
from .confidence import clarification_prompt, score_confidence
from .loaders import TelecomDB
from .planning import create_plan, refine_plan_with_llm
from .state import OrchestratorState, initial_orchestrator_state
from .tools import build_tool_registry


def build_orchestrator_graph(db: TelecomDB):
    graph = StateGraph(OrchestratorState)
    tools = build_tool_registry(db)

    def load_memory(state: OrchestratorState) -> dict:
        from memory.session_memory import SessionMemory
        from memory.user_profile import UserProfile
        from memory.vector_store import VectorMemory

        sid = state.get("session_id") or "default"
        session = SessionMemory(sid)
        profile = UserProfile(sid)
        profile.update_from_query(state["query"])
        mem = VectorMemory()
        recalled = mem.search(state["query"], k=3, session_id=sid)
        ctx = session.summary_context()
        profile_line = profile.context_line()
        mem_lines = "\n".join(f"- {r.get('text', '')[:200]}" for r in recalled)
        parts = [p for p in (ctx, profile_line, f"Recalled:\n{mem_lines}" if mem_lines else "") if p]
        return {
            "memory_context": "\n\n".join(parts).strip(),
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

    def confidence_gate(state: OrchestratorState) -> dict:
        plan_data = state.get("plan") or {}
        agents = plan_data.get("agents") or []
        explicit = {
            "analytics", "presentation", "eval", "deploy", "log",
            "drive_test", "prediction", "comparison", "compliance", "spec",
        }
        if len(agents) > 2 or any(a in agents for a in explicit):
            return {
                "needs_clarification": False,
                "confidence": 0.85,
                "steps": ["confidence:explicit_intent"],
            }

        scored = score_confidence(state["query"], db)
        if scored["needs_clarification"]:
            return {
                "needs_clarification": True,
                "confidence": scored["confidence"],
                "answer": clarification_prompt(state["query"]),
                "steps": ["confidence:clarify"],
            }
        return {
            "needs_clarification": False,
            "confidence": scored["confidence"],
            "steps": [f"confidence:{scored['confidence']}"],
        }

    def parallel_batch(state: OrchestratorState) -> dict:
        plan_data = state.get("plan") or {}
        agents = plan_data.get("parallel_agents") or []
        if not agents:
            agents = [a for a in (plan_data.get("agents") or []) if a not in ("presentation", "synthesizer", "verifier")]

        sid = state.get("session_id") or "default"
        outputs: list[dict] = list(state.get("agent_outputs") or [])
        artifacts: list[dict] = list(state.get("artifacts") or [])
        sources: list[dict] = list(state.get("sources") or [])
        steps: list[str] = []

        if not agents:
            return {"steps": ["parallel:empty"]}

        max_workers = min(8, max(1, len(agents)))

        def _run(name: str) -> dict:
            return run_agent(name, state["query"], db, tools, sid)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run, name): name for name in agents}
            for fut in as_completed(futures):
                out = fut.result()
                merged = merge_agent_result(
                    {"agent_outputs": outputs, "artifacts": artifacts, "sources": sources},
                    out,
                )
                outputs = merged["agent_outputs"]
                artifacts = merged["artifacts"]
                sources = merged["sources"]
                steps.extend(merged["steps"])

        return {
            "agent_outputs": outputs,
            "artifacts": artifacts,
            "sources": sources,
            "steps": steps + [f"parallel:{len(agents)}_agents"],
        }

    def sequential_tail(state: OrchestratorState) -> dict:
        plan_data = state.get("plan") or {}
        tail = [
            a for a in (plan_data.get("sequential_tail") or plan_data.get("agents") or [])
            if a in ("presentation", "synthesizer", "verifier")
        ]
        if "synthesizer" not in tail:
            tail.append("synthesizer")

        sid = state.get("session_id") or "default"
        outputs = list(state.get("agent_outputs") or [])
        artifacts = list(state.get("artifacts") or [])
        sources = list(state.get("sources") or [])
        answer = state.get("answer")
        steps: list[str] = []

        for name in tail:
            if name == "presentation":
                out = run_agent(
                    "presentation", state["query"], db, tools, sid, agent_outputs=outputs
                )
                merged = merge_agent_result(
                    {"agent_outputs": outputs, "artifacts": artifacts, "sources": sources},
                    out,
                )
                outputs, artifacts, sources = merged["agent_outputs"], merged["artifacts"], merged["sources"]
                steps.extend(merged["steps"])
            elif name == "synthesizer":
                out = run_agent(
                    "synthesizer", state["query"], db, tools, sid, agent_outputs=outputs
                )
                answer = out.get("content") or answer or ""
                artifacts.extend(out.get("artifacts") or [])
                sources.extend(out.get("sources") or [])
                steps.append("agent:synthesizer")
            elif name == "verifier":
                out = run_agent(
                    "verifier",
                    state["query"],
                    db,
                    tools,
                    sid,
                    agent_outputs=outputs,
                    answer=answer or "",
                )
                if out.get("content"):
                    answer = out["content"]
                outputs.append(out)
                steps.append("agent:verifier")

        return {
            "answer": answer or "",
            "agent_outputs": outputs,
            "artifacts": artifacts,
            "sources": sources,
            "steps": steps,
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

    def route_after_confidence(state: OrchestratorState) -> str:
        if state.get("needs_clarification") and state.get("answer"):
            return "save_memory"
        return "parallel_batch"

    graph.add_node("load_memory", load_memory)
    graph.add_node("plan", plan)
    graph.add_node("confidence_gate", confidence_gate)
    graph.add_node("parallel_batch", parallel_batch)
    graph.add_node("sequential_tail", sequential_tail)
    graph.add_node("save_memory", save_memory)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "plan")
    graph.add_edge("plan", "confidence_gate")
    graph.add_conditional_edges(
        "confidence_gate",
        route_after_confidence,
        {"save_memory": "save_memory", "parallel_batch": "parallel_batch"},
    )
    graph.add_edge("parallel_batch", "sequential_tail")
    graph.add_edge("sequential_tail", "save_memory")
    graph.add_edge("save_memory", END)

    if os.environ.get("TELECOMGPT_CHECKPOINT", "0") == "1":
        try:
            from langgraph.checkpoint.memory import MemorySaver

            return graph.compile(checkpointer=MemorySaver())
        except ImportError:
            pass

    return graph.compile()


def initial_state(
    query: str,
    history: list[dict[str, str]] | None = None,
    session_id: str = "default",
) -> OrchestratorState:
    return initial_orchestrator_state(query, history, session_id)
