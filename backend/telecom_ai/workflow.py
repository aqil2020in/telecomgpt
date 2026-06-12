"""Workflow management — task DAG, status tracking, error handling."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from .agents.taxonomy import agent_category

TaskStatus = Literal["pending", "running", "completed", "failed", "skipped"]


def build_tasks_from_plan(plan: dict) -> list[dict]:
    """Convert planner output into trackable workflow tasks."""
    agents = plan.get("agents") or []
    tasks: list[dict] = []
    for i, name in enumerate(agents):
        tasks.append({
            "id": f"t{i + 1}-{uuid.uuid4().hex[:6]}",
            "agent": name,
            "category": agent_category(name),
            "action": f"Run {name} agent",
            "status": "pending",
            "depends_on": [tasks[-1]["id"]] if tasks else [],
            "error": None,
            "started_at": None,
            "completed_at": None,
        })
    return tasks


def mark_task_running(tasks: list[dict], agent: str) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for t in tasks:
        if t["agent"] == agent and t["status"] == "pending":
            out.append({**t, "status": "running", "started_at": now})
        else:
            out.append(t)
    return out


def mark_task_completed(tasks: list[dict], agent: str, *, error: str | None = None) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    status: TaskStatus = "failed" if error else "completed"
    out = []
    for t in tasks:
        if t["agent"] == agent and t["status"] in ("pending", "running"):
            out.append({
                **t,
                "status": status,
                "error": error,
                "completed_at": now,
            })
        else:
            out.append(t)
    return out


def workflow_summary(tasks: list[dict]) -> dict[str, Any]:
    counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "skipped": 0}
    for t in tasks:
        counts[t.get("status", "pending")] = counts.get(t.get("status", "pending"), 0) + 1
    return {
        "total": len(tasks),
        "counts": counts,
        "failed_agents": [t["agent"] for t in tasks if t.get("status") == "failed"],
        "tasks": tasks,
    }


def handle_agent_error(agent: str, exc: Exception) -> dict:
    """Structured error for monitoring and optional re-planning."""
    return {
        "agent": agent,
        "error_type": type(exc).__name__,
        "message": str(exc)[:500],
        "recoverable": True,
    }
