"""External integrations — Web APIs, serverless, lightweight backends."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


def call_web_api(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    body: dict | None = None,
    timeout: float = 15,
) -> dict[str, Any]:
    """Generic lightweight HTTP client for external Web APIs."""
    data = json.dumps(body).encode() if body else None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return {"ok": True, "status": resp.status, "data": json.loads(raw)}
            except json.JSONDecodeError:
                return {"ok": True, "status": resp.status, "data": raw[:4000]}
    except URLError as e:
        return {"ok": False, "error": str(e.reason)}


def call_serverless_function(name: str, payload: dict | None = None) -> dict[str, Any]:
    """Invoke configured serverless endpoint (AWS Lambda URL, Cloud Function, etc.)."""
    base = os.environ.get("TELECOMGPT_SERVERLESS_URL", "").rstrip("/")
    if not base:
        return {"ok": False, "error": "TELECOMGPT_SERVERLESS_URL not configured"}
    url = f"{base}/{name}"
    token = os.environ.get("TELECOMGPT_SERVERLESS_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return call_web_api(url, method="POST", headers=headers, body=payload or {})


def list_integrations() -> list[dict]:
    return [
        {
            "name": "web_api",
            "description": "Generic REST/Web API calls",
            "configured": True,
        },
        {
            "name": "serverless",
            "description": "Serverless function hook (Lambda/Cloud Functions)",
            "configured": bool(os.environ.get("TELECOMGPT_SERVERLESS_URL")),
        },
        {
            "name": "openai_agents",
            "description": "OpenAI Assistants / tool-calling via TELECOMGPT_LLM=openai",
            "configured": bool(os.environ.get("OPENAI_API_KEY")),
        },
        {
            "name": "letta",
            "description": "Letta agent memory API",
            "configured": bool(os.environ.get("LETTA_API_URL")),
        },
        {
            "name": "mem0",
            "description": "Mem0 long-term memory (pip install mem0ai)",
            "configured": os.environ.get("TELECOMGPT_MEMORY") == "mem0",
        },
        {
            "name": "crewai",
            "description": "CrewAI role-based crews (TELECOMGPT_ENGINE=hybrid|crew)",
            "configured": _crewai_ok(),
        },
        {
            "name": "autogen",
            "description": "Microsoft AutoGen tool loops (TELECOMGPT_ENGINE=hybrid|autogen)",
            "configured": _autogen_ok(),
        },
        {
            "name": "tavily",
            "description": "Telecom web search (set TAVILY_API_KEY)",
            "configured": bool(os.environ.get("TAVILY_API_KEY")),
        },
    ]


def _crewai_ok() -> bool:
    try:
        from telecom_ai.engines.crew_runner import crew_available

        return crew_available()
    except Exception:
        return False


def _autogen_ok() -> bool:
    try:
        from telecom_ai.engines.autogen_runner import autogen_available

        return autogen_available()
    except Exception:
        return False
