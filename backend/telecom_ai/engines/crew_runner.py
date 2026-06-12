"""CrewAI integration — role-based crew as a LangGraph specialist agent."""

from __future__ import annotations

import os
from typing import Any


def crew_available() -> bool:
    try:
        import crewai  # noqa: F401

        return True
    except ImportError:
        return False


def _crew_fallback(query: str, tools: Any, memory_context: str | None, db: Any) -> dict:
    """Run research + KB + compliance sequentially when CrewAI unavailable."""
    from ..agents.extended import run_compliance_agent
    from ..agents.specialists import run_research_agent, run_telecom_kb_agent

    parts = []
    if memory_context:
        parts.append(f"**Memory context**\n{memory_context[:1500]}")

    if db:
        for runner, label in (
            (lambda: run_research_agent(query, tools), "Research"),
            (lambda: run_telecom_kb_agent(query, db, tools), "KB"),
            (lambda: run_compliance_agent(query, db, tools), "Compliance"),
        ):
            try:
                out = runner()
                if out.get("content"):
                    parts.append(f"**{label}**\n{out['content'][:2000]}")
            except Exception:
                pass

    return {
        "agent": "crew",
        "engine": "crew_fallback",
        "content": "\n\n".join(parts) if parts else "",
        "sources": [],
    }


def run_telecom_crew(
    query: str,
    tools: Any,
    db: Any,
    *,
    session_id: str = "default",
    memory_context: str | None = None,
) -> dict:
    """Execute a CrewAI crew (Researcher + RF Engineer + Compliance Analyst)."""
    if not crew_available():
        out = _crew_fallback(query, tools, memory_context, db)
        out["crewai_installed"] = False
        return out

    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("TELECOMGPT_LLM", "auto") != "ollama":
        out = _crew_fallback(query, tools, memory_context, db)
        out["note"] = "CrewAI requires OPENAI_API_KEY; used internal fallback crew."
        return out

    try:
        from crewai import Agent, Crew, Process, Task

        from .tool_bridge import build_crew_tools

        crew_tools = build_crew_tools(tools)
        ctx = (memory_context or "")[:2000]

        researcher = Agent(
            role="Telecom Research Analyst",
            goal="Find authoritative 3GPP and ShareTechnote references for the user query",
            backstory=f"Expert in 5G NR and LTE. Session context:\n{ctx}",
            tools=crew_tools[:4] or None,
            verbose=False,
            allow_delegation=False,
        )
        rf_engineer = Agent(
            role="RF Systems Engineer",
            goal="Apply band plans, device capabilities, and PHY calculations",
            backstory="Specialist in n77/n78, CA/EN-DC, ARFCN, and throughput.",
            tools=crew_tools[1:7] or None,
            verbose=False,
            allow_delegation=False,
        )
        analyst = Agent(
            role="Regulatory Analyst",
            goal="Check FCC/regulatory compliance for band and EIRP questions",
            backstory="Ensures answers respect licensed spectrum rules.",
            tools=crew_tools[:3] or None,
            verbose=False,
            allow_delegation=False,
        )

        research_task = Task(
            description=f"Research telecom references for: {query}",
            expected_output="Bullet summary with cited technical facts",
            agent=researcher,
        )
        rf_task = Task(
            description=f"Apply KB lookups and calculations for: {query}",
            expected_output="Band/device/PHY facts relevant to the query",
            agent=rf_engineer,
            context=[research_task],
        )
        compliance_task = Task(
            description=f"Add regulatory context for: {query}",
            expected_output="Short compliance note if applicable",
            agent=analyst,
            context=[research_task, rf_task],
        )

        crew = Crew(
            agents=[researcher, rf_engineer, analyst],
            tasks=[research_task, rf_task, compliance_task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff(inputs={"query": query, "session_id": session_id})
        content = str(result).strip()

        return {
            "agent": "crew",
            "engine": "crewai",
            "content": content,
            "crewai_installed": True,
            "tool_calls": [{"tool": "crew_kickoff", "ok": bool(content)}],
        }
    except Exception as e:
        out = _crew_fallback(query, tools, memory_context, db)
        out["crew_error"] = str(e)[:300]
        return out
