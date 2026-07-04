"""OpenAI narrative report generator (Phase 3 — with template fallback)."""

from __future__ import annotations

from typing import Any

from tnic.config import get_settings
from tnic.logging_config import get_logger
from tnic.models.schemas import RuleFinding

log = get_logger(__name__)


def generate_narrative_report(
    *,
    issue_type: str,
    query: str,
    findings: list[RuleFinding],
    kpis: dict[str, Any],
    rag_context: list[dict[str, str]],
) -> str:
    settings = get_settings()
    if settings.enable_openai_reports and settings.openai_api_key:
        try:
            return _openai_report(issue_type, query, findings, kpis, rag_context, settings)
        except Exception as e:
            log.warning("OpenAI report failed: %s — using template", e)
    return _template_report(issue_type, query, findings, kpis, rag_context)


def _template_report(
    issue_type: str,
    query: str,
    findings: list[RuleFinding],
    kpis: dict[str, Any],
    rag_context: list[dict[str, str]],
) -> str:
    lines = [
        f"# XYZ TNIC RCA Report — {issue_type.replace('_', ' ').title()}",
        "",
        f"**Query:** {query or 'N/A'}",
        "",
        "## Executive Summary",
        f"Analysis identified **{len(findings)}** rule-based finding(s). "
        f"Primary issue domain: **{issue_type}**.",
        "",
    ]
    if findings:
        top = findings[0]
        lines.append(
            f"Most probable root cause ({int(top.confidence * 100)}% confidence): **{top.probable_cause}**"
        )
    lines.extend(["", "## Key KPIs", ""])
    for k, v in list(kpis.items())[:10]:
        lines.append(f"- {k}: {v}")
    lines.extend(["", "## Findings", ""])
    for f in findings[:5]:
        lines.append(f"- [{f.category}] {f.probable_cause} (confidence {int(f.confidence*100)}%)")
    if rag_context:
        lines.extend(["", "## Knowledge Base References", ""])
        for r in rag_context[:3]:
            lines.append(f"- **{r.get('title')}**: {r.get('text', '')[:200]}...")
    lines.extend(["", "## Recommended Next Steps", ""])
    seen: set[str] = set()
    for f in findings:
        for a in f.recommended_actions:
            if a not in seen:
                lines.append(f"1. {a}")
                seen.add(a)
    return "\n".join(lines)


def _openai_report(
    issue_type: str,
    query: str,
    findings: list[RuleFinding],
    kpis: dict[str, Any],
    rag_context: list[dict[str, str]],
    settings: Any,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    findings_text = "\n".join(
        f"- {f.probable_cause} (confidence {f.confidence}, category {f.category})"
        for f in findings[:8]
    )
    rag_text = "\n".join(f"- {r.get('title')}: {r.get('text', '')[:300]}" for r in rag_context[:3])
    prompt = f"""You are a senior 5G network engineer at XYZ Telecom. Write a concise RCA report.

Issue type: {issue_type}
Query: {query}
KPIs: {kpis}
Rule findings:
{findings_text}

Knowledge base:
{rag_text}

Format: Executive summary, probable root cause, evidence, recommended actions, validation checklist.
Use telecom terminology (gNB, AMF, UPF, PRACH, HO, BLER, CQI). Be specific and actionable."""

    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
        temperature=0.3,
    )
    return resp.choices[0].message.content or _template_report(issue_type, query, findings, kpis, rag_context)
