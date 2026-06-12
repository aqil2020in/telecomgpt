"""Apply hybrid engine routing to planner output."""

from __future__ import annotations


def apply_engine_to_plan(plan: dict, flags: dict) -> dict:
    """Inject CrewAI / AutoGen agents based on TELECOMGPT_ENGINE mode."""
    from .engines.config import autonomous_agent_name, crew_enabled, engine_mode

    mode = engine_mode()
    auto = autonomous_agent_name()
    agents: list[str] = list(plan.get("agents") or [])

    # Replace react slot with autogen when hybrid/autogen mode
    agents = [auto if a == "react" else a for a in agents]

    if mode == "crew":
        agents = ["crew", "synthesizer"] if "synthesizer" in agents else ["crew"]
        if "verifier" in plan.get("agents", []):
            agents.append("verifier")

    elif crew_enabled():
        complexity = sum(
            1 for k, v in flags.items()
            if v and k in ("ppt", "compare", "compliance", "analytics", "spec", "predict")
        )
        if complexity >= 2 or flags.get("ppt"):
            if "crew" not in agents:
                agents.insert(0, "crew")
            # Crew subsumes these parallel specialists
            agents = [a for a in agents if a not in ("research", "telecom_kb", "compliance", "spec")]

    if mode == "autogen" and "autogen" not in agents:
        agents = [a if a not in ("react", "telecom_kb") else a for a in agents]
        if auto == "autogen" and "autogen" not in agents:
            insert_at = 1 if agents else 0
            agents.insert(insert_at, "autogen")

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for a in agents:
        if a not in seen:
            unique.append(a)
            seen.add(a)
    agents = unique

    parallel = [a for a in agents if a not in ("presentation", "synthesizer", "verifier")]
    sequential_tail = [a for a in agents if a in ("presentation", "verifier", "synthesizer")]

    plan["agents"] = agents
    plan["parallel_agents"] = parallel
    plan["sequential_tail"] = sequential_tail
    plan["engine"] = mode
    plan["autonomous_agent"] = auto
    plan["steps"] = [{"step": i + 1, "agent": a, "action": f"Run {a} agent"} for i, a in enumerate(agents)]
    if agents:
        plan["primary_agent"] = agents[0]
    return plan
