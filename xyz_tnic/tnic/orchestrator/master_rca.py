"""Master RCA — coverage correlation and multi-agent orchestration helpers."""

from __future__ import annotations

from typing import Any

from tnic.models.schemas import RuleFinding

# Coverage hole drives cross-domain failures (telecom causal chain)
COVERAGE_CORRELATION_MAP: dict[str, list[dict[str, str]]] = {
    "COVERAGE_HOLE": [
        {"domain": "handover", "impact": "HO Failure", "cause": "Coverage hole — HO prep/exec fails at cell edge"},
        {"domain": "rlf", "impact": "RLF", "cause": "Coverage hole — RLF from out-of-sync at weak RSRP"},
        {"domain": "call_drop", "impact": "Call Drops", "cause": "Coverage hole — mobility and radio drops"},
        {"domain": "rach", "impact": "RACH Failure", "cause": "Coverage hole — PRACH detection at cell edge"},
        {"domain": "throughput", "impact": "Throughput Degradation", "cause": "Coverage hole — low SINR caps MCS/TP"},
        {"domain": "complaint", "impact": "Customer Complaints", "cause": "Coverage hole — subscriber QoE complaints"},
    ],
    "WEAK_COVERAGE": [
        {"domain": "handover", "impact": "HO Failure", "cause": "Weak coverage — unstable mobility at boundary"},
        {"domain": "rlf", "impact": "RLF", "cause": "Weak coverage — radio link instability"},
        {"domain": "call_drop", "impact": "Call Drops", "cause": "Weak coverage — session release after RF loss"},
        {"domain": "rach", "impact": "RACH Failure", "cause": "Weak coverage — access failures"},
        {"domain": "throughput", "impact": "Throughput Degradation", "cause": "Weak coverage — throughput collapse"},
    ],
    "BEAM_COVERAGE_GAP": [
        {"domain": "beamforming", "impact": "Beam Congestion", "cause": "Beam gap — hot beams and edge instability"},
        {"domain": "throughput", "impact": "Throughput Degradation", "cause": "Beam congestion — PRB-limited TP"},
        {"domain": "handover", "impact": "HO Failure", "cause": "Beam switch stress at sector edge"},
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


def enrich_rca_with_coverage(
    findings: list[RuleFinding],
    cell_id: str | None,
    query: str = "",
) -> list[RuleFinding]:
    """Run RF Coverage Agent and merge correlated findings into Master RCA output."""
    try:
        import sys
        from pathlib import Path

        backend = Path(__file__).resolve().parents[2]
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))
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


def should_run_coverage_agent(query: str, issue_type: str | None = None) -> bool:
    ql = query.lower()
    if issue_type in ("rf_coverage", "coverage"):
        return True
    keys = (
        "coverage", "drive test", "geospatial", "rsrp heatmap",
        "coverage hole", "weak coverage", "hotspot", "3 mile", "3 mi",
    )
    return any(k in ql for k in keys)
