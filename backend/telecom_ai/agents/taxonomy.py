"""Agent taxonomy — task, retrieval, and autonomous agent classes."""

from __future__ import annotations

from typing import Literal

AgentCategory = Literal["task", "retrieval", "autonomous", "orchestration"]

AGENT_TAXONOMY: dict[str, dict] = {
    # Task agents — execute bounded workflows with tools
    "analytics": {"category": "task", "description": "CSV/Kaggle dashboards, charts, summaries"},
    "drive_test": {"category": "task", "description": "Drive-test SLA rules and RF maps"},
    "log": {"category": "task", "description": "UE/QXDM log parsing and error extraction"},
    "prediction": {"category": "task", "description": "KPI trend and correlation analysis"},
    "presentation": {"category": "task", "description": "PowerPoint report generation"},
    "comparison": {"category": "task", "description": "Device and technology comparison"},
    "compliance": {"category": "task", "description": "FCC/regulatory band checks"},
    "deploy": {"category": "task", "description": "Production health and deployment status"},
    "eval": {"category": "task", "description": "Smoke/regression eval on KB"},
    # Retrieval agents — search and cite knowledge
    "research": {"category": "retrieval", "description": "Hybrid RAG + memory search"},
    "spec": {"category": "retrieval", "description": "3GPP specification retrieval"},
    # Autonomous agents — dynamic tool selection / reasoning
    "telecom_kb": {"category": "autonomous", "description": "KB lookups with multi-tool reasoning"},
    "react": {"category": "autonomous", "description": "ReAct loop — LLM picks tools iteratively"},
    # Orchestration
    "synthesizer": {"category": "orchestration", "description": "Merge agent outputs into final answer"},
    "verifier": {"category": "orchestration", "description": "Cross-check answer against KB/RAG"},
}

TASK_AGENTS = [k for k, v in AGENT_TAXONOMY.items() if v["category"] == "task"]
RETRIEVAL_AGENTS = [k for k, v in AGENT_TAXONOMY.items() if v["category"] == "retrieval"]
AUTONOMOUS_AGENTS = [k for k, v in AGENT_TAXONOMY.items() if v["category"] == "autonomous"]


def agent_category(name: str) -> AgentCategory:
    return AGENT_TAXONOMY.get(name, {}).get("category", "task")  # type: ignore


def agents_by_category(category: AgentCategory) -> list[str]:
    return [k for k, v in AGENT_TAXONOMY.items() if v["category"] == category]


def taxonomy_summary() -> dict:
    return {
        "task_agents": TASK_AGENTS,
        "retrieval_agents": RETRIEVAL_AGENTS,
        "autonomous_agents": AUTONOMOUS_AGENTS,
        "all": list(AGENT_TAXONOMY.keys()),
        "details": AGENT_TAXONOMY,
    }
