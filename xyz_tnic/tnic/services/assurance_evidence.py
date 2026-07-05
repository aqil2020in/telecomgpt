"""Assurance evidence builder — correlates syslog/config/ANR/VoNR/alarm with RCA agents."""

from __future__ import annotations

from typing import Any

from tnic.models.schemas import RuleFinding
from tnic.services.assurance_ingestion import aggregate_assurance_kpis
from tnic.services.config_baseline import audit_configuration
from tnic.services.gnb_syslog_parser import parse_syslog_dataframe, parse_syslog_text

# Cross-domain correlation: assurance evidence → specialist agents
ASSURANCE_CORRELATIONS: dict[str, list[dict[str, str]]] = {
    "syslog": [
        {"agent": "handover", "impact": "HO Prep/Exec Failure", "cause": "Syslog HO_PREP_FAIL / XN_TIMEOUT"},
        {"agent": "rlf", "impact": "RLF", "cause": "Syslog T310_EXPIRY / out-of-sync pattern"},
        {"agent": "rach", "impact": "RACH Failure", "cause": "Syslog MSG1_FAIL / PRACH detection"},
        {"agent": "beamforming", "impact": "Beam Failure", "cause": "Syslog BEAM_OVERLOAD congestion"},
        {"agent": "transport", "impact": "Transport/SIP", "cause": "Syslog SIP_TIMEOUT on IMS path"},
        {"agent": "vonr", "impact": "VoNR Drop", "cause": "Syslog VONR/IMS bearer timeout"},
    ],
    "configuration": [
        {"agent": "handover", "impact": "Mobility tuning", "cause": "A3/TTT/hysteresis drift vs golden baseline"},
        {"agent": "anr", "impact": "Neighbor count", "cause": "CM neighbor_count below ANR threshold"},
        {"agent": "rach", "impact": "Access", "cause": "PRACH/TAC parameter mismatch"},
    ],
    "anr": [
        {"agent": "handover", "impact": "HO Prep Failure", "cause": "ANR missing neighbor / PCI conflict events"},
        {"agent": "rf_coverage", "impact": "Pilot pollution", "cause": "PCI conflict drives co-channel interference"},
        {"agent": "beamforming", "impact": "Beam confusion", "cause": "PCI/mod-3 collision on beam pair"},
    ],
    "vonr": [
        {"agent": "vonr", "impact": "VoNR Drop", "cause": "Session DROP with IMS_TIMEOUT or QOS_FLOW_FAIL"},
        {"agent": "rf_coverage", "impact": "Voice coverage", "cause": "VoNR drops cluster at cell edge"},
        {"agent": "latency", "impact": "IMS latency", "cause": "IMS_TIMEOUT cause in session trace"},
        {"agent": "core", "impact": "PDU/QoS", "cause": "QOS_FLOW_FAIL on 5QI-1 bearer setup"},
    ],
    "alarm": [
        {"agent": "transport", "impact": "Transport congestion", "cause": "Transport Packet Loss FM alarm active"},
        {"agent": "rlf", "impact": "RLF spike", "cause": "PTP sync / fronthaul alarm correlated with RLF"},
        {"agent": "beamforming", "impact": "Beam threshold", "cause": "Beam Threshold alarm on AAU"},
        {"agent": "rf_coverage", "impact": "Cell degraded", "cause": "Critical alarm before coverage KPI drop"},
    ],
}


def _confidence_from_counts(count: int, total: int, base: float = 0.72) -> float:
    if total <= 0:
        return base
    ratio = min(count / total, 1.0)
    return round(min(0.95, base + ratio * 0.22), 2)


def build_syslog_evidence(kpis: dict[str, Any]) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    text = kpis.get("syslog_text") or ""
    if not text and not kpis.get("syslog_event_count"):
        return findings

    parsed = parse_syslog_text(text) if text else []
    total = int(kpis.get("syslog_event_count") or 0)
    top_codes = kpis.get("syslog_event_codes") or {}

    if parsed or top_codes:
        top = sorted(top_codes.items(), key=lambda x: -x[1])[:5]
        conf = _confidence_from_counts(sum(top_codes.values()), max(total, 1), 0.78)
        findings.append(RuleFinding(
            rule_id="assurance_syslog_evidence",
            category="gnb_syslog",
            probable_cause=(
                f"Syslog evidence: {total} events — top codes: "
                + ", ".join(f"{c}({n})" for c, n in top[:3])
            ),
            confidence=conf,
            evidence={
                "source": "gnb_syslog.csv",
                "event_count": total,
                "event_codes": top_codes,
                "modules": kpis.get("syslog_modules", {}),
                "signatures_matched": [p["rule_id"] for p in parsed],
                "correlated_agents": [c["agent"] for c in ASSURANCE_CORRELATIONS["syslog"]],
            },
            recommended_actions=_syslog_recommendations(top_codes),
        ))

    for p in parsed:
        findings.append(RuleFinding(
            rule_id=p["rule_id"],
            category="gnb_syslog",
            probable_cause=f"[Syslog CSV] {p['probable_cause']}",
            confidence=p["confidence"],
            evidence={**p.get("evidence", {}), "source": "gnb_syslog.csv"},
            recommended_actions=p.get("recommended_actions", []),
        ))

    for item in ASSURANCE_CORRELATIONS["syslog"]:
        code_map = {
            "handover": kpis.get("syslog_ho_prep_fail_count", 0) + kpis.get("syslog_xn_timeout_count", 0),
            "rlf": kpis.get("syslog_t310_count", 0),
            "rach": kpis.get("syslog_msg1_fail_count", 0),
            "beamforming": kpis.get("syslog_beam_overload_count", 0),
            "transport": kpis.get("syslog_sip_timeout_count", 0),
            "vonr": kpis.get("syslog_sip_timeout_count", 0),
        }
        cnt = int(code_map.get(item["agent"], 0))
        if cnt > 0:
            findings.append(RuleFinding(
                rule_id=f"assurance_syslog_corr_{item['agent']}",
                category=item["agent"],
                probable_cause=f"[Syslog correlated] {item['cause']} ({cnt} events)",
                confidence=_confidence_from_counts(cnt, max(total, 1), 0.75),
                evidence={"correlation": "syslog", "impact": item["impact"], "event_count": cnt},
                recommended_actions=[f"Investigate {item['agent']} domain using syslog timeline"],
            ))
    return findings


def _syslog_recommendations(codes: dict[str, int]) -> list[str]:
    actions: list[str] = []
    if codes.get("HO_PREP_FAIL") or codes.get("XN_TIMEOUT"):
        actions.append("Check Xn/NG HO prep path and neighbor readiness")
    if codes.get("T310_EXPIRY"):
        actions.append("Map RLF cluster geography and correlate with RSRP/SINR")
    if codes.get("MSG1_FAIL"):
        actions.append("Audit PRACH configuration and UL interference")
    if codes.get("BEAM_OVERLOAD"):
        actions.append("Rebalance beam load and review scheduler weights")
    if codes.get("SIP_TIMEOUT"):
        actions.append("Trace IMS/SIP path and UPF QoS for 5QI-1")
    return actions or ["Attach gNB syslog excerpt to RCA ticket"]


def build_config_evidence(kpis: dict[str, Any]) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    drift = audit_configuration(kpis)
    if not drift and not kpis.get("ho_a3_offset_db"):
        return findings

    for d in drift:
        findings.append(RuleFinding(
            rule_id=d["rule_id"],
            category="config_audit",
            probable_cause=f"[CM CSV] {d['probable_cause']}",
            confidence=d["confidence"],
            evidence={**d.get("evidence", {}), "source": "cell_configuration.csv"},
            recommended_actions=d.get("recommended_actions", []),
        ))

    if drift:
        findings.append(RuleFinding(
            rule_id="assurance_config_evidence",
            category="config_audit",
            probable_cause=f"Configuration evidence: {len(drift)} parameter drift(s) from golden baseline",
            confidence=round(min(0.92, 0.78 + len(drift) * 0.04), 2),
            evidence={
                "source": "cell_configuration.csv",
                "drift_count": len(drift),
                "parameters": [d["evidence"].get("parameter") for d in drift],
                "correlated_agents": [c["agent"] for c in ASSURANCE_CORRELATIONS["configuration"]],
            },
            recommended_actions=["Compare live CM export vs golden JSON", "Rollback recent mobility parameter changes"],
        ))
    return findings


def build_anr_evidence(kpis: dict[str, Any]) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    total = int(kpis.get("anr_event_count") or 0)
    if total <= 0 and not kpis.get("missing_neighbor_count"):
        return findings

    pci = int(kpis.get("anr_pci_conflict_count") or kpis.get("pci_conflict_count") or 0)
    missing = int(kpis.get("anr_missing_neighbor_count") or kpis.get("missing_neighbor_count") or 0)
    add_fail = int(kpis.get("anr_add_fail_count") or 0)

    conf = _confidence_from_counts(pci + missing + add_fail, max(total, 1), 0.80)
    findings.append(RuleFinding(
        rule_id="assurance_anr_evidence",
        category="anr",
        probable_cause=(
            f"ANR evidence: {total} events — PCI conflict={pci}, missing neighbor={missing}, add fail={add_fail}"
        ),
        confidence=conf,
        evidence={
            "source": "anr_events.csv + neighbor_relations.csv",
            "anr_event_count": total,
            "event_types": kpis.get("anr_event_types", {}),
            "missing_neighbor_count": missing,
            "pci_conflict_count": pci,
            "nr_neighbor_count": kpis.get("nr_neighbor_count"),
            "correlated_agents": [c["agent"] for c in ASSURANCE_CORRELATIONS["anr"]],
        },
        recommended_actions=[
            "Run PCI audit and add missing NCR on HO corridor" if missing else "Clear ANR blacklist after fix",
            "Enable ANR PCI optimization" if pci else "Validate neighbor allow-list",
        ],
    ))

    for item in ASSURANCE_CORRELATIONS["anr"]:
        trigger = pci if item["agent"] in ("rf_coverage", "beamforming") else (missing + add_fail)
        if trigger > 0:
            findings.append(RuleFinding(
                rule_id=f"assurance_anr_corr_{item['agent']}",
                category=item["agent"],
                probable_cause=f"[ANR correlated] {item['cause']}",
                confidence=_confidence_from_counts(trigger, max(total, 1), 0.76),
                evidence={"correlation": "anr", "impact": item["impact"]},
                recommended_actions=[f"Run {item['agent']} RCA after ANR fix"],
            ))
    return findings


def build_vonr_evidence(kpis: dict[str, Any]) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    total = int(kpis.get("vonr_session_count") or 0)
    if total <= 0:
        return findings

    drop_rate = kpis.get("vonr_drop_rate") or 0
    conf = _confidence_from_counts(int(drop_rate * total / 100) if drop_rate else 0, total, 0.82)
    findings.append(RuleFinding(
        rule_id="assurance_vonr_evidence",
        category="vonr",
        probable_cause=(
            f"VoNR session evidence: {total} sessions, drop rate {drop_rate}%, "
            f"causes={kpis.get('vonr_drop_causes', {})}"
        ),
        confidence=conf,
        evidence={
            "source": "vonr_sessions.csv",
            "session_count": total,
            "vonr_drop_rate": drop_rate,
            "vonr_setup_success_rate": kpis.get("vonr_setup_success_rate"),
            "drop_causes": kpis.get("vonr_drop_causes", {}),
            "ims_timeout_count": kpis.get("ims_timeout_count"),
            "qos_flow_fail_count": kpis.get("qos_flow_fail_count"),
            "correlated_agents": [c["agent"] for c in ASSURANCE_CORRELATIONS["vonr"]],
        },
        recommended_actions=[
            "Check 5QI-1 QoS scheduler and IMS path" if kpis.get("qos_flow_fail_count") else "Improve NR voice coverage",
            "Trace SIP/RTP for IMS_TIMEOUT clusters",
        ],
    ))

    for item in ASSURANCE_CORRELATIONS["vonr"]:
        if drop_rate and drop_rate > 5:
            findings.append(RuleFinding(
                rule_id=f"assurance_vonr_corr_{item['agent']}",
                category=item["agent"],
                probable_cause=f"[VoNR correlated] {item['cause']}",
                confidence=round(min(0.90, conf - 0.05), 2),
                evidence={"correlation": "vonr", "impact": item["impact"], "vonr_drop_rate": drop_rate},
                recommended_actions=[f"Validate {item['agent']} KPIs during VoNR drop window"],
            ))
    return findings


def build_alarm_evidence(kpis: dict[str, Any]) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    total = int(kpis.get("active_alarm_count") or 0)
    if total <= 0:
        return findings

    critical = int(kpis.get("critical_alarm_count") or 0)
    conf = round(min(0.94, 0.80 + critical * 0.03 + total * 0.002), 2)
    findings.append(RuleFinding(
        rule_id="assurance_alarm_evidence",
        category="alarm",
        probable_cause=(
            f"Alarm correlation: {total} active alarms ({critical} CRITICAL) — "
            f"{kpis.get('active_alarms', '')}"
        ),
        confidence=conf,
        evidence={
            "source": "alarm_events.csv",
            "active_alarm_count": total,
            "critical_alarm_count": critical,
            "alarm_name_counts": kpis.get("alarm_name_counts", {}),
            "transport_alarm_count": kpis.get("transport_alarm_count"),
            "hw_alarm_count": kpis.get("hw_alarm_count"),
            "correlated_agents": [c["agent"] for c in ASSURANCE_CORRELATIONS["alarm"]],
        },
        recommended_actions=[
            "Clear root transport/HW alarm before RF optimization",
            "Build FM alarm timeline vs KPI degradation chart",
        ],
    ))

    for item in ASSURANCE_CORRELATIONS["alarm"]:
        cnt = 0
        if item["agent"] == "transport":
            cnt = int(kpis.get("transport_alarm_count") or 0)
        elif item["agent"] == "beamforming":
            cnt = int((kpis.get("alarm_name_counts") or {}).get("Beam Threshold", 0))
        elif item["agent"] in ("rlf", "rf_coverage"):
            cnt = int(kpis.get("hw_alarm_count") or 0)
        if cnt > 0:
            findings.append(RuleFinding(
                rule_id=f"assurance_alarm_corr_{item['agent']}",
                category=item["agent"],
                probable_cause=f"[Alarm correlated] {item['cause']} ({cnt} alarms)",
                confidence=_confidence_from_counts(cnt, max(total, 1), 0.77),
                evidence={"correlation": "alarm", "impact": item["impact"], "alarm_count": cnt},
                recommended_actions=[f"Resolve alarm then re-run {item['agent']} RCA"],
            ))
    return findings


def build_assurance_evidence(cell_id: str, kpis: dict[str, Any] | None = None) -> list[RuleFinding]:
    """Build all assurance evidence findings for Master RCA."""
    data = dict(kpis or {})
    if not data.get("assurance_sources"):
        data.update(aggregate_assurance_kpis(cell_id))

    findings: list[RuleFinding] = []
    findings.extend(build_syslog_evidence(data))
    findings.extend(build_config_evidence(data))
    findings.extend(build_anr_evidence(data))
    findings.extend(build_vonr_evidence(data))
    findings.extend(build_alarm_evidence(data))
    return findings


def assurance_recommendation_summary(findings: list[RuleFinding]) -> dict[str, Any]:
    """Aggregate recommendations and confidence from assurance evidence."""
    assurance = [f for f in findings if f.rule_id.startswith("assurance_")]
    if not assurance:
        return {"confidence": 0.0, "recommendations": [], "evidence_types": []}

    types = sorted({f.rule_id.replace("assurance_", "").split("_")[0] for f in assurance})
    actions: list[str] = []
    seen: set[str] = set()
    for f in sorted(assurance, key=lambda x: -x.confidence):
        for a in f.recommended_actions:
            if a not in seen:
                actions.append(a)
                seen.add(a)

    return {
        "confidence": round(max(f.confidence for f in assurance), 2),
        "mean_confidence": round(sum(f.confidence for f in assurance) / len(assurance), 2),
        "recommendations": actions[:8],
        "evidence_types": types,
        "finding_count": len(assurance),
    }
