"""Multi-agent orchestrator — LangGraph pipeline with memory, guardrails, workflow."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import END, START, StateGraph

from .agent_dispatch import merge_agent_result, run_agent
from .agents.taxonomy import agent_category
from .confidence import clarification_prompt, score_confidence
from .guardrails import check_input, check_output
from .loaders import TelecomDB
from .monitoring import RunMonitor, store_run_summary
from .planning import create_plan, refine_plan_with_llm
from .state import OrchestratorState, initial_orchestrator_state
from .tools import build_tool_registry
from .workflow import build_tasks_from_plan, handle_agent_error, mark_task_completed, mark_task_running


def build_orchestrator_graph(db: TelecomDB):
    graph = StateGraph(OrchestratorState)
    tools = build_tool_registry(db)
    _monitors: dict[str, RunMonitor] = {}

    def load_memory(state: OrchestratorState) -> dict:
        from memory.memory_manager import MemoryManager

        sid = state.get("session_id") or "default"
        mgr = MemoryManager(sid)
        ctx = mgr.assemble_context(state["query"])
        _monitors[sid] = RunMonitor(session_id=sid, query=state["query"])
        return {
            "memory_context": ctx,
            "steps": ["memory:loaded"],
        }

    def guardrails_pre(state: OrchestratorState) -> dict:
        result = check_input(state["query"])
        if not result["allowed"]:
            return {
                "answer": result["message"],
                "guardrail_issues": result["issues"],
                "needs_clarification": False,
                "steps": ["guardrails:blocked_input"],
            }
        redacted = result.get("redacted_query") or state["query"]
        issues = result.get("issues") or []
        return {
            "query": redacted,
            "guardrail_issues": issues,
            "steps": ["guardrails:input_ok"] if not issues else ["guardrails:input_redacted"],
        }

    def plan(state: OrchestratorState) -> dict:
        base = create_plan(state["query"], db)
        if os.environ.get("TELECOMGPT_LLM_PLAN", "1") == "1":
            base = refine_plan_with_llm(state["query"], base)
        tasks = build_tasks_from_plan(base)
        base["tasks"] = tasks
        base["agent_categories"] = {a: agent_category(a) for a in base.get("agents", [])}
        return {
            "plan": base,
            "workflow_tasks": tasks,
            "active_agent": base.get("primary_agent"),
            "steps": [f"plan:{len(base.get('steps', []))}_steps"],
        }

    def confidence_gate(state: OrchestratorState) -> dict:
        if state.get("answer") and "guardrails:blocked_input" in (state.get("steps") or []):
            return {"steps": ["confidence:skipped_blocked"]}

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
            agents = [
                a for a in (plan_data.get("agents") or [])
                if a not in ("presentation", "synthesizer", "verifier")
            ]

        sid = state.get("session_id") or "default"
        mem_ctx = state.get("memory_context") or ""
        history = state.get("history") or []
        outputs: list[dict] = list(state.get("agent_outputs") or [])
        artifacts: list[dict] = list(state.get("artifacts") or [])
        sources: list[dict] = list(state.get("sources") or [])
        steps: list[str] = []
        tasks = list(state.get("workflow_tasks") or [])
        monitor = _monitors.get(sid)

        if not agents:
            return {"steps": ["parallel:empty"]}

        max_workers = min(8, max(1, len(agents)))

        def _run(name: str) -> tuple[str, dict]:
            tools.current_agent = name
            t0 = time.perf_counter()
            try:
                out = run_agent(
                    name,
                    state["query"],
                    db,
                    tools,
                    sid,
                    memory_context=mem_ctx,
                    history=history,
                )
                if monitor:
                    monitor.record_agent_timing(name, time.perf_counter() - t0)
                return name, out
            except Exception as e:
                err = handle_agent_error(name, e)
                if monitor:
                    monitor.record_error(name, str(e))
                return name, {"agent": name, "content": "", "error": err}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run, name): name for name in agents}
            for fut in as_completed(futures):
                agent_name, out = fut.result()
                tasks = mark_task_running(tasks, agent_name)
                err = (out.get("error") or {}).get("message") if isinstance(out.get("error"), dict) else out.get("error")
                tasks = mark_task_completed(tasks, agent_name, error=str(err) if err else None)
                merged = merge_agent_result(
                    {"agent_outputs": outputs, "artifacts": artifacts, "sources": sources},
                    out,
                )
                outputs = merged["agent_outputs"]
                artifacts = merged["artifacts"]
                sources = merged["sources"]
                steps.extend(merged["steps"])

        tools.current_agent = None
        return {
            "agent_outputs": outputs,
            "artifacts": artifacts,
            "sources": sources,
            "workflow_tasks": tasks,
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
        mem_ctx = state.get("memory_context") or ""
        history = state.get("history") or []
        outputs = list(state.get("agent_outputs") or [])
        artifacts = list(state.get("artifacts") or [])
        sources = list(state.get("sources") or [])
        answer = state.get("answer")
        steps: list[str] = []
        tasks = list(state.get("workflow_tasks") or [])

        for name in tail:
            tools.current_agent = name
            tasks = mark_task_running(tasks, name)
            if name == "presentation":
                out = run_agent(
                    "presentation", state["query"], db, tools, sid,
                    agent_outputs=outputs, memory_context=mem_ctx, history=history,
                )
                merged = merge_agent_result(
                    {"agent_outputs": outputs, "artifacts": artifacts, "sources": sources},
                    out,
                )
                outputs, artifacts, sources = merged["agent_outputs"], merged["artifacts"], merged["sources"]
                steps.extend(merged["steps"])
                tasks = mark_task_completed(tasks, name)
            elif name == "synthesizer":
                out = run_agent(
                    "synthesizer", state["query"], db, tools, sid,
                    agent_outputs=outputs, memory_context=mem_ctx, history=history,
                )
                answer = out.get("content") or answer or ""
                artifacts.extend(out.get("artifacts") or [])
                sources.extend(out.get("sources") or [])
                steps.append("agent:synthesizer")
                tasks = mark_task_completed(tasks, name)
            elif name == "verifier":
                out = run_agent(
                    "verifier", state["query"], db, tools, sid,
                    agent_outputs=outputs, answer=answer or "",
                    memory_context=mem_ctx, history=history,
                )
                if out.get("content"):
                    answer = out["content"]
                outputs.append(out)
                steps.append("agent:verifier")
                tasks = mark_task_completed(tasks, name)

        tools.current_agent = None
        return {
            "answer": answer or "",
            "agent_outputs": outputs,
            "artifacts": artifacts,
            "sources": sources,
            "workflow_tasks": tasks,
            "steps": steps,
        }

    def guardrails_post(state: OrchestratorState) -> dict:
        answer = state.get("answer") or ""
        if not answer:
            return {"steps": ["guardrails:skip_empty"]}
        result = check_output(answer)
        issues = list(state.get("guardrail_issues") or [])
        issues.extend(result.get("issues") or [])
        return {
            "answer": result.get("filtered_answer") or answer,
            "guardrail_issues": issues,
            "steps": ["guardrails:output_ok"] if result["allowed"] else ["guardrails:output_filtered"],
        }

    def save_memory(state: OrchestratorState) -> dict:
        from memory.memory_manager import MemoryManager

        sid = state.get("session_id") or "default"
        mgr = MemoryManager(sid)
        answer = state.get("answer") or ""
        if answer:
            mgr.persist_exchange(state["query"], answer)
            plan_agents = (state.get("plan") or {}).get("agents") or []
            if plan_agents:
                mgr.store_procedure(
                    "last_successful_plan",
                    " → ".join(plan_agents),
                )

        monitor = _monitors.pop(sid, None)
        if monitor:
            for s in state.get("steps") or []:
                monitor.record_step(s)
            store_run_summary(monitor.finish(
                confidence=state.get("confidence"),
                guardrail_issues=state.get("guardrail_issues"),
            ))

        return {"steps": ["memory:saved"]}

    def route_after_guardrails_pre(state: OrchestratorState) -> str:
        if state.get("answer") and "guardrails:blocked_input" in (state.get("steps") or []):
            return "save_memory"
        return "plan"

    def route_after_confidence(state: OrchestratorState) -> str:
        if state.get("needs_clarification") and state.get("answer"):
            return "save_memory"
        return "parallel_batch"

    graph.add_node("load_memory", load_memory)
    graph.add_node("guardrails_pre", guardrails_pre)
    graph.add_node("plan", plan)
    graph.add_node("confidence_gate", confidence_gate)
    graph.add_node("parallel_batch", parallel_batch)
    graph.add_node("sequential_tail", sequential_tail)
    graph.add_node("guardrails_post", guardrails_post)
    graph.add_node("save_memory", save_memory)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "guardrails_pre")
    graph.add_conditional_edges(
        "guardrails_pre",
        route_after_guardrails_pre,
        {"save_memory": "save_memory", "plan": "plan"},
    )
    graph.add_edge("plan", "confidence_gate")
    graph.add_conditional_edges(
        "confidence_gate",
        route_after_confidence,
        {"save_memory": "save_memory", "parallel_batch": "parallel_batch"},
    )
    graph.add_edge("parallel_batch", "sequential_tail")
    graph.add_edge("sequential_tail", "guardrails_post")
    graph.add_edge("guardrails_post", "save_memory")
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
