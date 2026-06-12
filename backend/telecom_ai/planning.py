"""Autonomous planning — decompose user goals into agent steps."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .loaders import TelecomDB

AgentName = str

_PPT_KW = ("powerpoint", "ppt", "presentation", "slides", "slide deck", "report", "generate report", "excel")
_ANALYTICS_KW = ("csv", "chart", "plot", "dashboard", "kaggle", "analyze", "summarize", "drive test", "kpi", "rsrp", "throughput", "dataset")
_LOG_KW = ("log", "qxdm", "qcat", "rrc", "nas", "ue log")
_MAP_KW = ("map", "gps", "geo", "coverage map", "latitude", "longitude")
_PREDICT_KW = ("predict", "forecast", "trend", "anomaly", "ml")
_COMPLIANCE_KW = ("fcc", "regulatory", "compliance", "licensed", "eirp")
_SPEC_KW = ("3gpp", "ts 38", "ts 36", "specification", "spec clause", "38.331", "38.104")
_COMPARE_KW = ("compare", " vs ", " versus ", "difference", "better than")
_DEPLOY_KW = ("deploy", "health", "status", "render", "vercel", "production")
_EVAL_KW = ("eval", "evaluate", "smoke test", "regression test")
_RESEARCH_KW = ("sharetechnote", "reference", "how does", "explain", "what is")
_DEVICE_KW = ("s23", "s24", "s25", "iphone", "pixel", "device")
_CA_KW = ("ca", "carrier aggregation", "endc", "nrdc")
_PHY_KW = ("arfcn", "gscn", "throughput", "mhz", "ghz", "ssb")

ALL_AGENTS = (
    "telecom_kb", "research", "analytics", "drive_test", "log", "prediction",
    "compliance", "spec", "comparison", "react", "presentation", "verifier",
    "synthesizer", "deploy", "eval",
)


def create_plan(query: str, db: "TelecomDB | None" = None) -> dict:
    q = query.lower().strip()
    agents: list[AgentName] = []

    flags = {
        "ppt": any(k in q for k in _PPT_KW),
        "analytics": any(k in q for k in _ANALYTICS_KW),
        "log": any(k in q for k in _LOG_KW),
        "map": any(k in q for k in _MAP_KW),
        "predict": any(k in q for k in _PREDICT_KW),
        "compliance": any(k in q for k in _COMPLIANCE_KW),
        "spec": any(k in q for k in _SPEC_KW),
        "compare": any(k in q for k in _COMPARE_KW),
        "deploy": any(k in q for k in _DEPLOY_KW),
        "eval": any(k in q for k in _EVAL_KW),
        "research": any(k in q for k in _RESEARCH_KW),
        "kb": any(k in q for k in _DEVICE_KW + _CA_KW + _PHY_KW),
    }

    if flags["eval"]:
        agents = ["eval", "synthesizer"]
    elif flags["deploy"]:
        agents = ["deploy", "synthesizer"]
    elif flags["ppt"]:
        agents = ["research", "telecom_kb", "compliance", "presentation", "synthesizer", "verifier"]
    elif flags["log"]:
        agents = ["log", "research", "synthesizer", "verifier"]
    elif flags["map"] or ("drive" in q and "test" in q):
        agents = ["drive_test", "analytics", "prediction", "synthesizer", "verifier"]
    elif flags["predict"]:
        agents = ["prediction", "analytics", "research", "synthesizer"]
    elif flags["analytics"]:
        agents = ["analytics", "drive_test", "research", "react", "synthesizer", "verifier"]
    elif flags["compare"]:
        agents = ["comparison", "telecom_kb", "research", "synthesizer"]
    elif flags["compliance"]:
        agents = ["compliance", "telecom_kb", "synthesizer"]
    elif flags["spec"]:
        agents = ["spec", "research", "telecom_kb", "synthesizer"]
    elif flags["kb"] and not flags["research"]:
        agents = ["telecom_kb", "react", "synthesizer", "verifier"]
    elif flags["research"] or flags["kb"]:
        agents = ["telecom_kb", "research", "spec", "react", "synthesizer"]
    else:
        agents = ["research", "telecom_kb", "react", "synthesizer"]

    # Deduplicate preserving order
    seen = set()
    unique = []
    for a in agents:
        if a not in seen:
            unique.append(a)
            seen.add(a)
    agents = unique

    parallel = [a for a in agents if a not in ("presentation", "synthesizer", "verifier")]
    sequential_tail = [a for a in agents if a in ("presentation", "verifier", "synthesizer")]

    steps = [{"step": i + 1, "agent": a, "action": f"Run {a} agent"} for i, a in enumerate(agents)]

    return {
        "goal": query,
        "agents": agents,
        "parallel_agents": parallel,
        "sequential_tail": sequential_tail,
        "steps": steps,
        "primary_agent": agents[0],
        "parallel": True,
        "requires_tools": True,
        "requires_ppt": flags["ppt"],
    }


def refine_plan_with_llm(query: str, base_plan: dict) -> dict:
    from .reasoning import call_llm_json

    prompt = (
        f"User query: {query}\nDraft plan: {json.dumps(base_plan, indent=2)}\n\n"
        f"Return JSON with agents list using only: {', '.join(ALL_AGENTS)}"
    )
    refined = call_llm_json(prompt)
    if not refined or "agents" not in refined:
        return base_plan
    base_plan["agents"] = refined["agents"]
    base_plan["parallel_agents"] = [a for a in refined["agents"] if a not in ("presentation", "synthesizer", "verifier")]
    return base_plan


def parse_tool_calls(text: str) -> list[dict]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        match = re.search(r"(\{[^{}]*\"tool\"[^{}]*\})", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
        if isinstance(data, list):
            return data
        if "tools" in data:
            return data["tools"]
        if "tool" in data:
            return [data]
    except json.JSONDecodeError:
        pass
    return []
