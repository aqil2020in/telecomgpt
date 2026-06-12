"""Engine mode configuration — LangGraph hub with CrewAI / AutoGen spokes."""

from __future__ import annotations

import os


def engine_mode() -> str:
    """langgraph | crew | autogen | hybrid (default)."""
    return os.environ.get("TELECOMGPT_ENGINE", "hybrid").strip().lower()


def autonomous_agent_name() -> str:
    """Which autonomous agent replaces react in plans."""
    explicit = os.environ.get("TELECOMGPT_AUTONOMOUS", "").strip().lower()
    if explicit in ("react", "autogen"):
        return explicit
    if engine_mode() in ("hybrid", "autogen"):
        return "autogen"
    return "react"


def crew_enabled() -> bool:
    return engine_mode() in ("hybrid", "crew")


def autogen_enabled() -> bool:
    return engine_mode() in ("hybrid", "autogen") or autonomous_agent_name() == "autogen"


def engine_status() -> dict:
    from .crew_runner import crew_available
    from .autogen_runner import autogen_available

    return {
        "mode": engine_mode(),
        "autonomous_agent": autonomous_agent_name(),
        "crew_enabled": crew_enabled(),
        "autogen_enabled": autogen_enabled(),
        "crewai_installed": crew_available(),
        "autogen_installed": autogen_available(),
        "master_orchestrator": "langgraph",
    }
