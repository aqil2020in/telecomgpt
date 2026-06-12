"""Guardrails — input/output filtering, tool policies, compliance."""

from __future__ import annotations

import re
from typing import Any

from .agents.taxonomy import agent_category

# Basic content patterns (extend for production moderation APIs)
_BLOCKED_INPUT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\b(hack|exploit)\s+(cell|network|base\s*station)\b",
        r"\b(jam|jammer)\s+(signal|frequency)\b",
        r"\b(bypass|disable)\s+(authentication|encryption)\s+(on|for)\s+(network|carrier)\b",
    )
]

_BLOCKED_OUTPUT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\bstep-by-step\s+to\s+(hack|attack)\b",
        r"\billegal\s+intercept\b",
    )
]

# Per-category tool allowlists (empty = all tools allowed for category)
TOOL_POLICY: dict[str, set[str] | None] = {
    "task": None,
    "retrieval": {
        "hybrid_search", "rag_search", "memory_search", "web_search", "live_reference_fetch",
        "lookup_glossary",
    },
    "autonomous": None,
    "orchestration": set(),
}

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"\bIMSI[:\s]*\d{10,15}\b", re.I),
    re.compile(r"\bIMEI[:\s]*\d{14,16}\b", re.I),
]


def check_input(query: str) -> dict[str, Any]:
    """Pre-orchestration input guardrails."""
    issues: list[str] = []
    for pat in _BLOCKED_INPUT_PATTERNS:
        if pat.search(query):
            issues.append("policy:harmful_intent")
            break

    redacted = query
    for pat in PII_PATTERNS:
        if pat.search(query):
            issues.append("pii:detected_in_input")
            redacted = pat.sub("[REDACTED]", redacted)

    blocked = "policy:harmful_intent" in issues
    return {
        "allowed": not blocked,
        "blocked": blocked,
        "issues": issues,
        "redacted_query": redacted,
        "message": (
            "I can't help with requests that appear to involve unauthorized network access "
            "or signal interference. Ask about legitimate RF engineering, 3GPP specs, or device capabilities."
            if blocked
            else ""
        ),
    }


def check_output(answer: str) -> dict[str, Any]:
    """Post-synthesis output guardrails."""
    issues: list[str] = []
    filtered = answer

    for pat in _BLOCKED_OUTPUT_PATTERNS:
        if pat.search(answer):
            issues.append("policy:unsafe_output")
            filtered = "I can't provide that information. I can help with standard telecom engineering topics instead."

    for pat in PII_PATTERNS:
        if pat.search(filtered):
            issues.append("pii:redacted_in_output")
            filtered = pat.sub("[REDACTED]", filtered)

    return {
        "allowed": "policy:unsafe_output" not in issues,
        "issues": issues,
        "filtered_answer": filtered,
    }


def tool_allowed(agent_name: str, tool_name: str) -> bool:
    """Check if an agent category may invoke a tool."""
    cat = agent_category(agent_name)
    allowed = TOOL_POLICY.get(cat)
    if allowed is None:
        return True
    return tool_name in allowed


def compliance_notice() -> str:
    return (
        "TelecomGPT follows responsible-AI guidelines: no unauthorized network access guidance, "
        "PII redaction on IMSI/IMEI, FCC/regulatory context for band queries, and verifier cross-checks on KB answers."
    )
