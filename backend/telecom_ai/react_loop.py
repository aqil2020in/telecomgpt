"""Optional ReAct-style LLM tool-calling loop."""

from __future__ import annotations

import json
import os
from typing import Any


def run_react_tools(query: str, tool_specs: list[dict], tool_registry: Any, *, max_steps: int = 3) -> dict:
    """Run up to max_steps of LLM-proposed tool calls."""
    from .reasoning import _call_configured_llm

    names = [t["name"] for t in tool_specs[:12]]
    prompt = (
        f"User query: {query}\n\n"
        f"Available tools: {', '.join(names)}\n\n"
        "Reply with JSON only: {\"tools\": [{\"tool\": \"name\", \"arguments\": {{}}}]}\n"
        "Pick 1-2 tools max."
    )
    raw = _call_configured_llm(prompt, "", history=None)
    if not raw:
        return {"agent": "react", "content": "", "tool_calls": []}

    calls = _parse_tools(raw)
    results = []
    for call in calls[:max_steps]:
        name = call.get("tool") or call.get("name")
        args = call.get("arguments") or call.get("args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        tr = tool_registry.run(name, **args)
        results.append({"tool": name, "ok": tr.ok, "output": tr.output if tr.ok else tr.error})

    summary = "\n".join(f"- {r['tool']}: {str(r['output'])[:400]}" for r in results if r.get("ok"))
    return {"agent": "react", "content": summary, "tool_calls": results}


def _parse_tools(text: str) -> list[dict]:
    import re

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        if isinstance(data, list):
            return data
        return data.get("tools", [data] if data.get("tool") else [])
    except json.JSONDecodeError:
        return []
