"""OpenAI RCA Narrator — structured narrative from Master RCA output."""

from __future__ import annotations

import json
from typing import Any

from tnic.config import Settings, get_settings
from tnic.logging_config import get_logger
from tnic.models.schemas import RCANarrativeReport, RCAResponse, RuleFinding

log = get_logger(__name__)

_KPI_EVIDENCE_KEYS = (
    "cell_id",
    "ss_rsrp",
    "ss_sinr",
    "cqi",
    "ho_success_rate",
    "ho_prep_fail_rate",
    "rach_success_rate",
    "rlf_rate",
    "call_drop_rate",
    "throughput_mbps",
    "prb_utilization",
    "upf_latency_ms",
    "latency_ms",
)


class OpenAIRCANarrator:
    """Generates executive RCA narratives from Master RCA orchestrator output."""

    def narrate(self, rca: RCAResponse, kpis: dict[str, Any] | None = None) -> RCANarrativeReport:
        settings = get_settings()
        if settings.enable_openai_reports and settings.openai_api_key:
            try:
                return self._openai_narrative(rca, kpis or {}, settings)
            except Exception as exc:
                log.warning("OpenAI RCA narrator failed: %s — using template", exc)
        return self._template_narrative(rca, kpis or {})

    def _template_narrative(self, rca: RCAResponse, kpis: dict[str, Any]) -> RCANarrativeReport:
        top = rca.findings[0] if rca.findings else None
        confidence = _overall_confidence(rca, top)
        cell_id = kpis.get("cell_id") or _cell_from_evidence(rca)

        if top:
            root_cause = top.probable_cause
            domain = rca.issue_type.replace("_", " ")
            executive = (
                f"Master RCA for {domain} on cell **{cell_id or 'cluster'}** identified "
                f"{len(rca.findings)} finding(s) across {len(rca.agents_run)} specialist agent(s). "
                f"The dominant root cause is **{root_cause[:120]}** "
                f"with {int(confidence * 100)}% confidence."
            )
        else:
            root_cause = "No dominant rule fired — review KPIs and event traces manually."
            executive = (
                f"Master RCA completed for **{rca.issue_type}** with no rule findings. "
                "Manual investigation recommended."
            )

        evidence = _collect_evidence(rca, kpis)
        recommendations = _collect_recommendations(rca)

        return RCANarrativeReport(
            executive_summary=executive,
            root_cause=root_cause,
            evidence=evidence,
            recommendations=recommendations,
            confidence=round(confidence, 2),
            source="template",
        )

    def _openai_narrative(
        self,
        rca: RCAResponse,
        kpis: dict[str, Any],
        settings: Settings,
    ) -> RCANarrativeReport:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        payload = _rca_payload(rca, kpis)
        prompt = f"""You are a senior 5G network engineer at XYZ Telecom.
Convert the Master RCA JSON below into a structured RCA narrative.

Return ONLY valid JSON with these keys:
- executive_summary (string, 2-3 sentences)
- root_cause (string, single primary cause)
- evidence (array of strings, 3-6 bullet facts from KPIs/findings)
- recommendations (array of strings, 3-5 actionable steps)
- confidence (number 0.0-1.0)

Use telecom terminology (gNB, AMF, UPF, PRACH, HO, BLER, CQI). Be specific.

Master RCA:
{json.dumps(payload, default=str)[:6000]}"""

        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        template = self._template_narrative(rca, kpis)
        return RCANarrativeReport(
            executive_summary=str(data.get("executive_summary") or template.executive_summary),
            root_cause=str(data.get("root_cause") or template.root_cause),
            evidence=_as_string_list(data.get("evidence")) or template.evidence,
            recommendations=_as_string_list(data.get("recommendations")) or template.recommendations,
            confidence=_clamp_confidence(data.get("confidence"), template.confidence),
            source="openai",
        )


def narrate_master_rca(
    rca: RCAResponse,
    kpis: dict[str, Any] | None = None,
) -> RCANarrativeReport:
    """Generate structured RCA narrative from Master RCA orchestrator output."""
    return OpenAIRCANarrator().narrate(rca, kpis=kpis)


def generate_narrative_report(
    *,
    issue_type: str = "",
    query: str = "",
    findings: list[RuleFinding] | None = None,
    kpis: dict[str, Any] | None = None,
    rag_context: list[dict[str, str]] | None = None,
    rca: RCAResponse | None = None,
) -> str:
    """Backward-compatible markdown report API."""
    if rca is None:
        rca = _rca_from_parts(
            issue_type=issue_type,
            query=query,
            findings=findings or [],
            kpis=kpis or {},
            rag_context=rag_context or [],
        )
    return narrate_master_rca(rca, kpis=kpis).to_markdown()


def generate_structured_report(
    *,
    rca: RCAResponse,
    kpis: dict[str, Any] | None = None,
) -> RCANarrativeReport:
    """Structured narrator output with Executive Summary, Root Cause, Evidence, etc."""
    return narrate_master_rca(rca, kpis=kpis)


def _rca_from_parts(
    *,
    issue_type: str,
    query: str,
    findings: list[RuleFinding],
    kpis: dict[str, Any],
    rag_context: list[dict[str, str]],
) -> RCAResponse:
    probable = [
        {
            "cause": f.probable_cause,
            "confidence": f.confidence,
            "category": f.category,
            "evidence": f.evidence,
        }
        for f in findings[:5]
    ]
    actions: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        for action in finding.recommended_actions:
            if action not in seen:
                actions.append(action)
                seen.add(action)
    return RCAResponse(
        issue_type=issue_type or "unknown",
        query=query,
        agents_run=[],
        findings=findings,
        probable_root_causes=probable,
        recommended_actions=actions[:10],
        validation_checklist=[],
        rag_context=rag_context,
    )


def _rca_payload(rca: RCAResponse, kpis: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_type": rca.issue_type,
        "query": rca.query,
        "agents_run": rca.agents_run,
        "health_score": rca.health_score,
        "kpis": {k: kpis[k] for k in _KPI_EVIDENCE_KEYS if kpis.get(k) is not None},
        "findings": [
            {
                "category": f.category,
                "probable_cause": f.probable_cause,
                "confidence": f.confidence,
                "evidence": f.evidence,
                "recommended_actions": f.recommended_actions,
            }
            for f in rca.findings[:8]
        ],
        "probable_root_causes": rca.probable_root_causes[:5],
        "recommended_actions": rca.recommended_actions[:8],
        "validation_checklist": rca.validation_checklist[:5],
        "rag_context": rca.rag_context[:3],
    }


def _collect_evidence(rca: RCAResponse, kpis: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    seen: set[str] = set()

    for key in _KPI_EVIDENCE_KEYS:
        value = kpis.get(key)
        if value is not None:
            line = f"KPI {key}: {value}"
            if line not in seen:
                evidence.append(line)
                seen.add(line)

    for finding in rca.findings[:5]:
        line = f"[{finding.category}] {finding.probable_cause} ({int(finding.confidence * 100)}%)"
        if line not in seen:
            evidence.append(line)
            seen.add(line)
        for ek, ev in list(finding.evidence.items())[:3]:
            detail = f"{finding.category}.{ek}: {ev}"
            if detail not in seen:
                evidence.append(detail)
                seen.add(detail)

    if rca.health_score is not None:
        evidence.append(f"Cell health score: {rca.health_score}")

    for item in rca.rag_context[:2]:
        title = item.get("title", "Knowledge base")
        text = str(item.get("text", ""))[:160]
        line = f"KB — {title}: {text}"
        if line not in seen:
            evidence.append(line)
            seen.add(line)

    return evidence[:8]


def _collect_recommendations(rca: RCAResponse) -> list[str]:
    recs: list[str] = []
    seen: set[str] = set()
    for action in rca.recommended_actions:
        if action not in seen:
            recs.append(action)
            seen.add(action)
    for finding in rca.findings:
        for action in finding.recommended_actions:
            if action not in seen:
                recs.append(action)
                seen.add(action)
    for item in rca.validation_checklist:
        if item not in seen:
            recs.append(item)
            seen.add(item)
    return recs[:8]


def _overall_confidence(rca: RCAResponse, top: RuleFinding | None) -> float:
    if top:
        return top.confidence
    if rca.probable_root_causes:
        return float(rca.probable_root_causes[0].get("confidence") or 0.55)
    return 0.55


def _cell_from_evidence(rca: RCAResponse) -> str | None:
    for finding in rca.findings:
        cell = finding.evidence.get("cell_id")
        if cell:
            return str(cell)
    return None


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _clamp_confidence(value: Any, fallback: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return round(fallback, 2)
    return round(min(max(score, 0.0), 1.0), 2)
