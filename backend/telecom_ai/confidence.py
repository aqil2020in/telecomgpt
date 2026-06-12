"""Confidence scoring and clarification routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .loaders import TelecomDB


def score_confidence(query: str, db: "TelecomDB", agent_outputs: list[dict] | None = None) -> dict:
    """Return confidence 0-1 and whether to ask for clarification."""
    q = query.lower().strip()
    score = 0.35
    reasons: list[str] = []

    if db.glossary_lookup(query):
        score += 0.35
        reasons.append("glossary_hit")
    if db.answer_device(query) or db.answer_ca_endc_nrdc(query) or db.answer_phy_math(query):
        score += 0.25
        reasons.append("kb_handler")
    if db.answer_comparison(query):
        score += 0.2
        reasons.append("comparison")

    outputs = agent_outputs or []
    if any(o.get("agent") == "analytics" and o.get("artifacts") for o in outputs):
        score += 0.15
        reasons.append("analytics_data")
    if any(o.get("sources") for o in outputs):
        score += 0.1
        reasons.append("rag_sources")

    if len(q.split()) <= 2 and q not in ("hi", "hello", "hey"):
        score -= 0.15
        reasons.append("short_query")

    score = max(0.0, min(1.0, score))
    needs_clarification = score < 0.35 and len(q.split()) < 4

    return {
        "confidence": round(score, 2),
        "needs_clarification": needs_clarification,
        "reasons": reasons,
    }


def clarification_prompt(query: str) -> str:
    return (
        "I need a bit more context to give a precise telecom answer.\n\n"
        f"You asked: \"{query}\"\n\n"
        "Could you specify:\n"
        "• Technology (5G NR / LTE)?\n"
        "• Band (e.g. n78, n77) or device (S24, iPhone)?\n"
        "• Or upload a drive-test CSV / log file for analysis?"
    )
