"""Master RCA — coverage correlation, workflow enrichment, multi-agent orchestration."""

from __future__ import annotations

from typing import Any

from tnic.models.schemas import RuleFinding
from tnic.orchestrator.workflow_registry import WORKFLOW_REGISTRY, detect_workflow
from tnic.services.gnb_syslog_parser import parse_syslog_text

# Coverage hole drives cross-domain failures (telecom causal chain)
COVERAGE_CORRELATION_MAP: dict[str, list[dict[str, str]]] = {
    "COVERAGE_HOLE": [
        {"domain": "handover", "impact": "HO Failure", "cause": "Coverage hole — HO prep/exec fails at cell edge"},
        {"domain": "rlf", "impact": "RLF", "cause": "Coverage hole — RLF from out-of-sync at weak RSRP"},
        {"domain": "call_drop", "impact": "Call Drops", "cause": "Coverage hole — mobility and radio drops"},
        {"domain": "rach", "impact": "RACH Failure", "cause": "Coverage hole — PRACH detection at cell edge"},
        {"domain": "throughput", "impact": "Throughput Degradation", "cause": "Coverage hole — low SINR caps MCS/TP"},
        {"domain": "vonr", "impact": "VoNR Failure", "cause": "Coverage hole — 5QI-1 bearer unstable at edge"},
        {"domain": "complaint", "impact": "Customer Complaints", "cause": "Coverage hole — subscriber QoE complaints"},
    ],
    "WEAK_COVERAGE": [
        {"domain": "handover", "impact": "HO Failure", "cause": "Weak coverage — unstable mobility at boundary"},
        {"domain": "rlf", "impact": "RLF", "cause": "Weak coverage — radio link instability"},
        {"domain": "call_drop", "impact": "Call Drops", "cause": "Weak coverage — session release after RF loss"},
        {"domain": "rach", "impact": "RACH Failure", "cause": "Weak coverage — access failures"},
        {"domain": "throughput", "impact": "Throughput Degradation", "cause": "Weak coverage — throughput collapse"},
        {"domain": "vonr", "impact": "VoNR Degradation", "cause": "Weak coverage — voice quality/MOS impact"},
    ],
    "BEAM_COVERAGE_GAP": [
        {"domain": "beamforming", "impact": "Beam Congestion", "cause": "Beam gap — hot beams and edge instability"},
        {"domain": "throughput", "impact": "Throughput Degradation", "cause": "Beam congestion — PRB-limited TP"},
        {"domain": "handover", "impact": "HO Failure", "cause": "Beam switch stress at sector edge"},
    ],
}

# Industry workflow → cross-domain correlations (Pradeep Dhote RCA framework)
WORKFLOW_CORRELATION_MAP: dict[str, list[dict[str, str]]] = {
    "call_drop": [
        {"domain": "rlf", "impact": "RLF spike", "cause": "Call drop workflow — check RLF pattern first"},
        {"domain": "handover", "impact": "HO Failure", "cause": "Call drop workflow — HO >5% triggers mobility RCA"},
        {"domain": "rf_coverage", "impact": "Coverage hole", "cause": "Call drop workflow — weak RSRP/RSRQ at drop location"},
        {"domain": "throughput", "impact": "PRB congestion", "cause": "Call drop workflow — PDCCH/PUCCH congestion check"},
        {"domain": "config_audit", "impact": "CM drift", "cause": "Call drop workflow — recent parameter change audit"},
    ],
    "handover_failure": [
        {"domain": "anr", "impact": "Missing neighbor", "cause": "HO workflow — verify NCL and ANR add/remove"},
        {"domain": "rf_coverage", "impact": "Coverage overlap", "cause": "HO workflow — overlap/overshoot on A3/TTT corridor"},
        {"domain": "config_audit", "impact": "A3/TTT drift", "cause": "HO workflow — audit mobility parameters vs golden"},
    ],
    "rach_rrc_failure": [
        {"domain": "rf_coverage", "impact": "Weak RSRP", "cause": "RACH workflow — RF below access threshold"},
        {"domain": "config_audit", "impact": "PRACH config", "cause": "RACH workflow — prach-ConfigurationIndex mismatch"},
        {"domain": "core", "impact": "AMF unreachable", "cause": "RACH workflow — N2/AMF accessibility check"},
    ],
    "low_dl_throughput": [
        {"domain": "beamforming", "impact": "Beam failure", "cause": "TP workflow — 5G beamforming success check"},
        {"domain": "transport", "impact": "Backhaul", "cause": "TP workflow — DU↔CU↔UPF packet loss"},
    ],
    "vonr_5g_sa": [
        {"domain": "core", "impact": "SMF/AMF", "cause": "VoNR workflow — PDU session and 5QI flow setup"},
        {"domain": "rf_coverage", "impact": "NR coverage", "cause": "VoNR workflow — NR coverage hole blocks voice"},
        {"domain": "config_audit", "impact": "5QI profile", "cause": "VoNR workflow — 5QI-1/65 profile validation"},
    ],
    "cell_outage": [
        {"domain": "gnb_syslog", "impact": "HW/F1 alarm", "cause": "Outage workflow — DU/CU crash or fronthaul cut"},
        {"domain": "transport", "impact": "Link down", "cause": "Outage workflow — backhaul/fronthaul status"},
    ],
}

PRIMARY_TO_CODE = {
    "Coverage Deficiency": "COVERAGE_HOLE",
    "Coverage Hole": "COVERAGE_HOLE",
    "Weak Coverage": "WEAK_COVERAGE",
    "Beam Congestion": "BEAM_COVERAGE_GAP",
    "Interference Dominant": "INTERFERENCE",
}


def coverage_findings_from_summary(summary: dict[str, Any]) -> list[RuleFinding]:
    """Convert RF coverage summary into Master RCA findings + correlated impacts."""
    if not summary or summary.get("primary_issue") == "No Data":
        return []

    findings: list[RuleFinding] = []
    primary = summary.get("primary_issue", "")
    code = PRIMARY_TO_CODE.get(primary, "COVERAGE_HOLE")

    findings.append(RuleFinding(
        rule_id="rf_coverage_primary",
        category="rf_coverage",
        probable_cause=(
            f"{primary}: {summary.get('recommendation', '')} "
            f"(score {summary.get('coverage_score')}, confidence {int(float(summary.get('confidence', 0)) * 100)}%)"
        ),
        confidence=float(summary.get("confidence", 0.75)),
        evidence={
            "cell_id": summary.get("cell_id"),
            "coverage_score": summary.get("coverage_score"),
            "secondary_issue": summary.get("secondary_issue"),
            "metrics": summary.get("metrics", {}),
            "issue_counts": summary.get("issue_counts", {}),
        },
        recommended_actions=[summary.get("recommendation", "Re-drive 3 mi cluster")],
    ))

    if summary.get("secondary_issue"):
        findings.append(RuleFinding(
            rule_id="rf_coverage_secondary",
            category="rf_coverage",
            probable_cause=f"Secondary: {summary['secondary_issue']}",
            confidence=float(summary.get("confidence", 0.75)) - 0.05,
            evidence={"cell_id": summary.get("cell_id")},
            recommended_actions=["Address secondary beam/RF issue after primary coverage fix"],
        ))

    for item in COVERAGE_CORRELATION_MAP.get(code, []):
        findings.append(RuleFinding(
            rule_id=f"coverage_corr_{item['domain']}",
            category=item["domain"],
            probable_cause=f"[Coverage correlated] {item['cause']}",
            confidence=round(float(summary.get("confidence", 0.75)) - 0.08, 2),
            evidence={
                "correlation": "coverage_drives_" + item["impact"].lower().replace(" ", "_"),
                "impact": item["impact"],
                "source_cell": summary.get("cell_id"),
            },
            recommended_actions=[f"Resolve coverage on {summary.get('cell_id')} to clear {item['impact']}"],
        ))

    return findings


def workflow_correlation_findings(query: str, cell_id: str | None = None) -> list[RuleFinding]:
    """Emit industry workflow correlation findings when query matches a known workflow."""
    wf = detect_workflow(query)
    if not wf:
        return []
    spec = WORKFLOW_REGISTRY.get(wf, {})
    findings: list[RuleFinding] = []
    findings.append(RuleFinding(
        rule_id=f"workflow_{wf}",
        category="workflow",
        probable_cause=f"[Workflow: {spec.get('title', wf)}] Domains: {', '.join(spec.get('domains', []))}",
        confidence=0.88,
        evidence={
            "workflow_key": wf,
            "agents": spec.get("agents", []),
            "pm_counters": spec.get("pm_counters", []),
            "validation": spec.get("validation", []),
            "cell_id": cell_id,
        },
        recommended_actions=[f"Run agents: {', '.join(spec.get('agents', []))}"],
    ))
    for item in WORKFLOW_CORRELATION_MAP.get(wf, []):
        findings.append(RuleFinding(
            rule_id=f"workflow_corr_{wf}_{item['domain']}",
            category=item["domain"],
            probable_cause=f"[{spec.get('title', wf)}] {item['cause']}",
            confidence=0.80,
            evidence={"workflow": wf, "impact": item["impact"], "cell_id": cell_id},
            recommended_actions=[f"Validate: {item['impact']}"],
        ))
    return findings


def enrich_rca_with_coverage(
    findings: list[RuleFinding],
    cell_id: str | None,
    query: str = "",
) -> list[RuleFinding]:
    """Run RF Coverage Agent and merge correlated findings into Master RCA output."""
    try:
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        agents_dir = root / "agents"
        if agents_dir.exists() and str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from agents.rf_coverage_agent import RFCoverageAgent

        cid = cell_id or RFCoverageAgent()._cell_from_query(query) or "XYZ401"
        summary = RFCoverageAgent().analyze_cell(str(cid)).to_json_record()
        cov_findings = coverage_findings_from_summary(summary)
        existing_ids = {f.rule_id for f in findings}
        for f in cov_findings:
            if f.rule_id not in existing_ids:
                findings.append(f)
    except Exception:
        pass
    return findings


def enrich_rca_with_workflow(
    findings: list[RuleFinding],
    cell_id: str | None,
    query: str = "",
) -> list[RuleFinding]:
    """Add industry workflow correlation block."""
    wf_findings = workflow_correlation_findings(query, cell_id)
    existing_ids = {f.rule_id for f in findings}
    for f in wf_findings:
        if f.rule_id not in existing_ids:
            findings.append(f)
    return findings


def enrich_rca_with_syslog(
    findings: list[RuleFinding],
    query: str = "",
    kpis: dict[str, Any] | None = None,
) -> list[RuleFinding]:
    """Parse syslog signatures from query/log excerpt."""
    text = query
    if kpis:
        text = str(kpis.get("syslog_text") or kpis.get("log_excerpt") or query)
    if not any(k in text.lower() for k in ("ngap", "rlf", "rach", "vonr", "crash", "xnap", "prach", "rrc")):
        return findings
    parsed = parse_syslog_text(text)
    existing_ids = {f.rule_id for f in findings}
    for p in parsed:
        if p["rule_id"] not in existing_ids:
            findings.append(RuleFinding(
                rule_id=p["rule_id"],
                category="gnb_syslog",
                probable_cause=p["probable_cause"],
                confidence=p["confidence"],
                evidence=p.get("evidence", {}),
                recommended_actions=p.get("recommended_actions", []),
            ))
    return findings


def enrich_master_rca(
    findings: list[RuleFinding],
    cell_id: str | None,
    query: str = "",
    kpis: dict[str, Any] | None = None,
) -> list[RuleFinding]:
    """Full Master RCA enrichment pipeline."""
    findings = enrich_rca_with_workflow(findings, cell_id, query)
    if should_run_coverage_agent(query) or cell_id:
        findings = enrich_rca_with_coverage(findings, cell_id, query)
    findings = enrich_rca_with_syslog(findings, query, kpis)
    return findings


def should_run_coverage_agent(query: str, issue_type: str | None = None) -> bool:
    ql = query.lower()
    if issue_type in ("rf_coverage", "coverage"):
        return True
    keys = (
        "coverage", "drive test", "geospatial", "rsrp heatmap",
        "coverage hole", "weak coverage", "hotspot", "3 mile", "3 mi",
    )
    return any(k in ql for k in keys)
