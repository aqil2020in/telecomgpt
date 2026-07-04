"""Master RCA orchestrator — coordinates specialist agents and knowledge graph."""

from __future__ import annotations

from typing import Any

from app.agents.specialists import AGENT_REGISTRY, kpi_to_dict
from app.logging_config import get_logger
from app.models.schemas import AnalyzeRequest, KnowledgeGraph, KnowledgeGraphEdge, KnowledgeGraphNode, RCAResponse, RuleFinding
from app.orchestrator.knowledge_graph import build_knowledge_graph
from app.rules import RULE_ENGINES, detect_issue_type
from app.services.health_scoring import compute_health_score
from app.services.report_generator import generate_narrative_report

log = get_logger(__name__)

# Agents to run per primary issue (multi-domain RCA)
ORCHESTRATION_MAP = {
    "handover": ["handover", "rlf", "pm"],
    "rlf": ["rlf", "handover", "call_drop", "pm"],
    "call_drop": ["call_drop", "rlf", "handover", "beamforming", "core"],
    "throughput": ["throughput", "beamforming", "transport", "pm"],
    "rach": ["rach", "beamforming", "pm"],
    "beamforming": ["beamforming", "throughput", "call_drop"],
    "latency": ["latency", "transport", "core"],
    "transport": ["transport", "latency", "throughput"],
    "core": ["core", "latency", "call_drop"],
    "complaint": ["complaint", "handover", "throughput", "call_drop"],
}


class MasterRCAOrchestrator:
    def run(self, request: AnalyzeRequest, rag_context: list[dict[str, str]] | None = None) -> RCAResponse:
        issue = detect_issue_type(request.query, request.issue_type)
        kpis = kpi_to_dict(request.kpis)
        if request.complaint_text:
            issue = detect_issue_type(request.complaint_text, request.issue_type)

        agent_names = ORCHESTRATION_MAP.get(issue, [issue, "pm"])
        all_findings: list[RuleFinding] = []
        agents_run: list[str] = []

        for name in agent_names:
            agent = AGENT_REGISTRY.get(name)
            if not agent:
                continue
            result = agent.analyze(kpis, query=request.query or request.complaint_text or "")
            agents_run.append(result.agent)
            all_findings.extend(result.findings)

        # Also run primary rule engine directly for completeness
        engine = RULE_ENGINES.get(issue)
        if engine:
            for f in engine.evaluate(kpis):
                if not any(x.rule_id == f["rule_id"] for x in all_findings):
                    all_findings.append(RuleFinding(**f))

        all_findings.sort(key=lambda x: x.confidence, reverse=True)

        probable = [
            {"cause": f.probable_cause, "confidence": f.confidence, "category": f.category, "evidence": f.evidence}
            for f in all_findings[:5]
        ]
        actions: list[str] = []
        seen: set[str] = set()
        for f in all_findings:
            for a in f.recommended_actions:
                if a not in seen:
                    actions.append(a)
                    seen.add(a)

        checklist = _validation_checklist(issue)
        health = compute_health_score(kpis)
        kg = build_knowledge_graph(
            complaint=request.complaint_text or request.query,
            issue_type=issue,
            kpis=kpis,
            findings=all_findings,
            actions=actions[:5],
        )

        narrative = None
        if request.generate_report:
            narrative = generate_narrative_report(
                issue_type=issue,
                query=request.query,
                findings=all_findings,
                kpis=kpis,
                rag_context=rag_context or [],
            )

        return RCAResponse(
            issue_type=issue,
            query=request.query or request.complaint_text or "",
            agents_run=agents_run,
            findings=all_findings,
            probable_root_causes=probable,
            recommended_actions=actions[:10],
            validation_checklist=checklist,
            health_score=health["overall_score"],
            knowledge_graph=kg,
            rag_context=rag_context or [],
            narrative_report=narrative,
        )


def _validation_checklist(issue: str) -> list[str]:
    common = [
        "Verify fix holds for 24h monitoring window",
        "Re-run drive test or PM export on affected cells",
        "Document root cause and action in incident record",
    ]
    specific = {
        "handover": ["HO success rate restored to SLA", "No prep-fail spike on neighbor pair"],
        "throughput": ["Mean DL throughput meets target", "CQI/BLER within fair band"],
        "call_drop": ["Drop rate below operator threshold", "Re-establishment success OK"],
        "rach": ["RACH success rate normalized", "Msg3 retx rate acceptable"],
        "latency": ["RTT p95 within SLA", "5QI mapping verified"],
    }
    return specific.get(issue, []) + common
