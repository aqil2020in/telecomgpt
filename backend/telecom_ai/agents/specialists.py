"""Specialist agents for TelecomGPT multi-agent orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..loaders import TelecomDB
    from ..tools import ToolRegistry


def run_telecom_kb_agent(query: str, db: "TelecomDB", tools: "ToolRegistry") -> dict:
    """Structured KB + calculator agent."""
    parts: list[str] = []
    tool_calls: list[dict] = []

    from analytics.link_budget import looks_like_link_budget_query

    if looks_like_link_budget_query(query):
        result = tools.run("explain_link_budget", query=query)
        if result.ok and result.output:
            md = result.output.get("markdown") if isinstance(result.output, dict) else str(result.output)
            if md:
                return {
                    "agent": "telecom_kb",
                    "content": md,
                    "tool_calls": [{"tool": "explain_link_budget", "ok": True}],
                }

    for tool, arg_key in (
        ("lookup_device", "query"),
        ("lookup_ca_endc", "query"),
        ("calc_phy", "query"),
        ("lookup_bands", "query"),
    ):
        result = tools.run(tool, **{arg_key: query})
        if result.ok and result.output and result.output not in ("Not found", "No device match", "No CA/EN-DC match", "Could not compute"):
            parts.append(f"**{tool}**\n{result.output}")
            tool_calls.append({"tool": tool, "ok": True})

    gloss = tools.run("lookup_glossary", term=query)
    if gloss.ok and gloss.output != "Not found":
        parts.append(f"**Glossary**\n{gloss.output}")
        tool_calls.append({"tool": "lookup_glossary", "ok": True})

    comparison = db.answer_comparison(query)
    if comparison:
        parts.append(f"**Comparison**\n{comparison}")

    kb_ctx = db.context_for(query)
    if kb_ctx:
        parts.append(f"**KB context**\n{kb_ctx[:2000]}")

    return {
        "agent": "telecom_kb",
        "content": "\n\n".join(parts) if parts else "",
        "tool_calls": tool_calls,
    }


def run_research_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    """RAG + vector memory research agent."""
    tool_calls: list[dict] = []
    parts: list[str] = []

    rag = tools.run("hybrid_search", query=query, session_id=session_id, k=6)
    cites: list[dict] = []
    if rag.ok and rag.output:
        context, cites = rag.output if isinstance(rag.output, tuple) else (str(rag.output), [])
        parts.append(f"**Reference excerpts (RAG + live ShareTechnote/sqimway/3GPP + web)**\n{context[:4500]}")
        tool_calls.append({"tool": "hybrid_search", "ok": True, "citations": cites})

    mem = tools.run("memory_search", query=query, session_id=session_id, k=3)
    if mem.ok and mem.output:
        mem_text = "\n".join(f"- {m.get('text', '')[:300]}" for m in mem.output[:3])
        if mem_text.strip():
            parts.append(f"**Memory recall**\n{mem_text}")
            tool_calls.append({"tool": "memory_search", "ok": True})

    return {
        "agent": "research",
        "content": "\n\n".join(parts),
        "tool_calls": tool_calls,
        "sources": rag.output[1] if rag.ok and isinstance(rag.output, tuple) else [],
    }


def run_analytics_agent(query: str, tools: "ToolRegistry") -> dict:
    """Analytics agent — Kaggle CSVs, summaries, and Plotly charts."""
    from analytics.kaggle_charts import build_kaggle_dashboard

    parts: list[str] = []
    tool_calls: list[dict] = []
    artifacts: list[dict] = []

    dashboard = build_kaggle_dashboard(query)
    if dashboard.get("ok"):
        s = dashboard["summary"]
        parts.append(
            f"**Kaggle analytics: {dashboard['dataset']}**\n"
            f"Rows: {s.get('rows')}, Columns: {s.get('columns')}, GPS: {s.get('has_gps')}\n"
            f"RF columns: {s.get('rf_columns')}\n"
            f"Generated {len(dashboard.get('charts', []))} chart(s) — see below in chat."
        )
        for ch in dashboard.get("charts", []):
            if ch.get("ok"):
                artifacts.append(ch)
        tool_calls.append({"tool": "kaggle_dashboard", "ok": True, "dataset": dashboard["dataset"]})
    else:
        csvs = tools.run("list_kaggle_csvs")
        if csvs.ok and csvs.output:
            tool_calls.append({"tool": "list_kaggle_csvs", "ok": True})
            lines = ["Available Kaggle CSV files:"]
            for f in csvs.output[:5]:
                path = f.get("path", "")
                lines.append(f"- {f.get('name', path)}")
                summary = tools.run("csv_summary", path=path)
                if summary.ok:
                    sv = summary.output
                    lines.append(f"  rows={sv.get('rows')}, cols={sv.get('columns')}")
            parts.append("\n".join(lines))
        else:
            parts.append(dashboard.get("error", "No analytics data available."))

    return {
        "agent": "analytics",
        "content": "\n\n".join(parts),
        "tool_calls": tool_calls,
        "artifacts": artifacts,
    }


def run_presentation_agent(
    query: str,
    combined_content: str,
    tools: "ToolRegistry",
    session_id: str = "default",
) -> dict:
    """Presentation agent — generate PowerPoint."""
    topic = query.replace("powerpoint", "").replace("ppt", "").replace("presentation", "").strip()
    topic = topic[:100] if topic else "TelecomGPT Report"

    result = tools.run(
        "generate_presentation",
        topic=topic.title(),
        content=combined_content,
        session_id=session_id,
    )
    artifact = None
    content = ""
    if result.ok and isinstance(result.output, dict):
        artifact = result.output
        if result.output.get("ok"):
            content = (
                f"PowerPoint report generated: **{result.output.get('filename')}**\n"
                f"Slides: {result.output.get('slides')}\n"
                f"Download: {result.output.get('download_url')}"
            )
        else:
            content = f"PPT generation failed: {result.output.get('error')}"
    return {
        "agent": "presentation",
        "content": content,
        "artifact": artifact,
        "tool_calls": [{"tool": "generate_presentation", "ok": bool(artifact and artifact.get("ok"))}],
    }


def run_synthesizer(
    query: str,
    agent_outputs: list[dict],
    db: "TelecomDB",
    history: list[dict[str, str]] | None = None,
    memory_context: str | None = None,
) -> dict:
    """Merge agent outputs into final answer via LLM or template."""
    from ..reasoning import llm_answer_with_sources

    # Deterministic computed reports (link budget) — preserve tables, skip LLM rewrite.
    for o in agent_outputs:
        tools_used = {t.get("tool") for t in (o.get("tool_calls") or []) if t.get("ok")}
        if o.get("agent") == "rf_metrics" and "explain_link_budget" in tools_used and o.get("content"):
            all_sources: list[dict] = []
            for ao in agent_outputs:
                all_sources.extend(ao.get("sources") or [])
            artifacts = [o.get("artifact") for o in agent_outputs if o.get("artifact")]
            for ao in agent_outputs:
                for a in ao.get("artifacts") or []:
                    if a and a not in artifacts:
                        artifacts.append(a)
            return {
                "agent": "synthesizer",
                "content": o["content"],
                "sources": all_sources,
                "artifacts": [a for a in artifacts if a],
            }

    combined = "\n\n---\n\n".join(
        f"[{o.get('agent', 'agent')}]\n{o.get('content', '')}"
        for o in agent_outputs
        if o.get("content")
    )

    if memory_context:
        combined = f"[Session & long-term memory]\n{memory_context[:3000]}\n\n---\n\n{combined}".strip()

    artifacts = [o.get("artifact") for o in agent_outputs if o.get("artifact")]
    for o in agent_outputs:
        for a in o.get("artifacts") or []:
            if a and a not in artifacts:
                artifacts.append(a)
    all_sources: list[dict] = []
    for o in agent_outputs:
        all_sources.extend(o.get("sources") or [])

    if combined.strip():
        answer, llm_sources = llm_answer_with_sources(
            query,
            db,
            history=history,
            extra_context=combined,
        )
        all_sources.extend(llm_sources)
    else:
        answer, llm_sources = llm_answer_with_sources(query, db, history=history)
        all_sources.extend(llm_sources)

    if not answer and combined.strip():
        answer = combined[:6000]

    return {
        "agent": "synthesizer",
        "content": answer,
        "sources": all_sources,
        "artifacts": [a for a in artifacts if a],
    }
