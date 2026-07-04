"""Master RCA orchestrator — coordinates specialist agents and knowledge graph."""

from __future__ import annotations

from typing import Any

from tnic.agents.specialists import AGENT_REGISTRY, kpi_to_dict
from tnic.logging_config import get_logger
from tnic.models.schemas import AnalyzeRequest, KnowledgeGraph, KnowledgeGraphEdge, KnowledgeGraphNode, RCAResponse, RuleFinding
from tnic.orchestrator.knowledge_graph import build_knowledge_graph
from tnic.orchestrator.master_rca import enrich_rca_with_coverage, should_run_coverage_agent
from tnic.rules import RULE_ENGINES, detect_issue_type
from tnic.services.health_scoring import compute_health_score
from tnic.services.report_generator import narrate_master_rca

log = get_logger(__name__)

# Agents to run per primary issue (multi-domain RCA)
ORCHESTRATION_MAP = {
    "handover": ["handover", "rlf", "pm", "latency", "transport"],
    "rlf": ["rlf", "handover", "call_drop", "pm"],
    "call_drop": ["call_drop", "rlf", "handover", "beamforming", "core", "transport", "latency"],
    "throughput": ["throughput", "beamforming", "transport", "pm"],
    "rach": ["rach", "beamforming", "pm"],
    "beamforming": ["beamforming", "throughput", "call_drop"],
    "latency": ["latency", "transport", "core"],
    "transport": ["transport", "latency", "throughput"],
    "core": ["core", "latency", "call_drop"],
    "complaint": ["complaint", "handover", "throughput", "call_drop", "rf_coverage"],
    "rf_coverage": ["rf_coverage", "rlf", "handover", "call_drop", "rach", "throughput", "beamforming", "complaint"],
    "coverage": ["rf_coverage", "rlf", "handover", "call_drop", "rach", "throughput", "beamforming"],
}

# Primary-domain boost so RLF/HO queries rank domain findings above cross-agent noise.
_PRIMARY_DOMAIN_BOOST = 0.10
_CLASSIFIER_BOOST = 0.15

_ISSUE_CATEGORY = {
    "handover": "handover",
    "ho": "handover",
    "rlf": "rlf",
    "call_drop": "call_drop",
    "throughput": "throughput",
    "rach": "rach",
    "beamforming": "beamforming",
    "beam": "beamforming",
    "latency": "latency",
    "rf_coverage": "rf_coverage",
    "coverage": "rf_coverage",
}


def _rank_score(finding: RuleFinding, issue_type: str) -> float:
    score = finding.confidence
    if finding.category == _ISSUE_CATEGORY.get(issue_type, issue_type):
        score += _PRIMARY_DOMAIN_BOOST
    if finding.rule_id.endswith("_class"):
        score += _CLASSIFIER_BOOST
    return score


def rank_findings(findings: list[RuleFinding], issue_type: str) -> list[RuleFinding]:
    return sorted(findings, key=lambda f: _rank_score(f, issue_type), reverse=True)


class MasterRCAOrchestrator:
    def run(self, request: AnalyzeRequest, rag_context: list[dict[str, str]] | None = None) -> RCAResponse:
        issue = detect_issue_type(request.query, request.issue_type)
        kpis = kpi_to_dict(request.kpis)
        if request.complaint_text:
            issue = detect_issue_type(request.complaint_text, request.issue_type)

        # Merge bundled telecom dataset KPIs for any missing keys (demo + production cells).
        try:
            from tnic.datasets.kpi_service import kpis_for_rca

            ds_kpis = kpis_for_rca(
                query=request.query or request.complaint_text or "",
                cell_id=kpis.get("cell_id"),
            )
            for k, v in ds_kpis.items():
                if v is not None and kpis.get(k) is None:
                    kpis[k] = v
        except Exception as e:
            log.warning("Dataset KPI enrichment skipped: %s", e)

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

        if issue == "call_drop":
            from tnic.services.drop_classifier import drop_classification_finding

            clf = drop_classification_finding(kpis)
            if clf and not any(x.rule_id == clf["rule_id"] for x in all_findings):
                all_findings.append(RuleFinding(**clf))

        if should_run_coverage_agent(request.query or "", request.issue_type) or kpis.get("cell_id"):
            all_findings = enrich_rca_with_coverage(
                all_findings,
                str(kpis.get("cell_id")) if kpis.get("cell_id") else None,
                query=request.query or request.complaint_text or "",
            )

        all_findings = rank_findings(all_findings, issue)

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
        narrative_structured = None
        if request.generate_report:
            partial = RCAResponse(
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
            )
            narrative_structured = narrate_master_rca(partial, kpis=kpis)
            narrative = narrative_structured.to_markdown()

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
            narrative_structured=narrative_structured,
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
