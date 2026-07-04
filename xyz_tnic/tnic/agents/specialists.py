"""Specialist agents — thin wrappers over rule engines."""

from __future__ import annotations

from typing import Any

from tnic.agents.base import BaseAgent, kpi_to_dict
from tnic.agents.ho_agent import HandoverFailureAgent
from tnic.models.schemas import AgentResult
from tnic.rules import RULE_ENGINES
from tnic.rules.beamforming_rules import BEAMFORMING_RULE_ENGINE
from tnic.rules.call_drop_rules import CALL_DROP_RULE_ENGINE
from tnic.rules.ho_rules import HO_RULE_ENGINE
from tnic.rules.latency_rules import LATENCY_RULE_ENGINE
from tnic.rules.rach_rules import RACH_RULE_ENGINE
from tnic.rules.rlf_rules import RLF_RULE_ENGINE
from tnic.rules.throughput_rules import THROUGHPUT_RULE_ENGINE


class _RuleAgent(BaseAgent):
    def __init__(self, name: str, engine):
        self.name = name
        self._engine = engine

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        data = kpi_to_dict(kpis)
        findings = self._engine.evaluate(data)
        summary = f"{self.name}: {len(findings)} rule(s) fired."
        if findings:
            summary += f" Top: {findings[0]['probable_cause'][:80]}"
        return self._findings_to_result(findings, summary)


class HOAgent(BaseAgent):
    name = "ho_agent"

    def __init__(self):
        self._failure_agent = HandoverFailureAgent()

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        data = kpi_to_dict(kpis)
        diagnosis = self._failure_agent.analyze_kpis(data, query=query)
        findings: list[dict[str, Any]] = []
        if diagnosis.failure_type not in ("No Data", "No Failure"):
            findings.append({
                "rule_id": f"ho_{diagnosis.evidence.get('failure_code', 'unknown').lower() if diagnosis.evidence else 'detected'}",
                "category": "handover",
                "probable_cause": f"{diagnosis.failure_type}: {diagnosis.root_cause}",
                "confidence": diagnosis.confidence,
                "evidence": diagnosis.evidence or {},
                "recommended_actions": _ho_actions(diagnosis.evidence.get("failure_code") if diagnosis.evidence else None),
            })
        # Also run legacy rule engine on KPI aggregates for additional findings
        legacy = HO_RULE_ENGINE.evaluate(data)
        seen = {f["probable_cause"][:60] for f in findings}
        for f in legacy:
            if f["probable_cause"][:60] not in seen:
                findings.append(f)
        findings.sort(key=lambda x: x["confidence"], reverse=True)
        summary = f"{self.name}: {diagnosis.failure_type} (confidence {diagnosis.confidence:.2f})"
        return self._findings_to_result(findings, summary)


def _ho_actions(code: str | None) -> list[str]:
    actions = {
        "PREP_FAILURE": ["Verify Xn connectivity", "Check neighbor relation for target PCI", "Review HO prep timer"],
        "EXEC_FAILURE": ["Compare source/target RSRP at HO", "Audit HO parameters A3/A5", "Drive-test HO corridor"],
        "XN_FAILURE": ["Check Xn transport and IPsec/SCTP", "Verify Xn neighbor relation", "Review XnAP cause codes"],
        "N2_FAILURE": ["Check AMF load and NGAP timers", "Verify N2 connectivity", "Inspect NGAP HandoverFailure cause"],
        "TOO_EARLY_HO": ["Increase A3 offset or time-to-trigger", "Review cell individual offsets"],
        "TOO_LATE_HO": ["Decrease A3 offset", "Add filler cell on HO corridor"],
        "PING_PONG": ["Increase hysteresis", "Review CIO between neighbor pair"],
        "WRONG_CELL": ["Verify neighbor list completeness", "Check SSB beam priority"],
    }
    return actions.get(code or "", ["Review handover_events.csv and mobility parameters"])


class RLFAgent(_RuleAgent):
    def __init__(self):
        super().__init__("rlf_agent", RLF_RULE_ENGINE)


class CallDropAgent(_RuleAgent):
    def __init__(self):
        super().__init__("call_drop_agent", CALL_DROP_RULE_ENGINE)


class ThroughputAgent(_RuleAgent):
    def __init__(self):
        super().__init__("throughput_agent", THROUGHPUT_RULE_ENGINE)


class RACHAgent(_RuleAgent):
    def __init__(self):
        super().__init__("rach_agent", RACH_RULE_ENGINE)


class BeamformingAgent(_RuleAgent):
    def __init__(self):
        super().__init__("beamforming_agent", BEAMFORMING_RULE_ENGINE)


class LatencyAgent(_RuleAgent):
    def __init__(self):
        super().__init__("latency_agent", LATENCY_RULE_ENGINE)


class PMAgent(BaseAgent):
    name = "pm_agent"

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        from tnic.services.pm_ingestion import validate_pm_kpis

        issues = validate_pm_kpis(kpi_to_dict(kpis))
        findings = []
        for i, issue in enumerate(issues[:5]):
            findings.append({
                "rule_id": f"pm_validation_{i}",
                "category": "pm_validation",
                "probable_cause": issue,
                "confidence": 0.65,
                "evidence": {},
                "recommended_actions": ["Reconcile PM counter definitions", "Verify KPI derivation formula"],
            })
        return self._findings_to_result(findings, f"PM validation: {len(issues)} issue(s).")


class TransportAgent(BaseAgent):
    name = "transport_agent"

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        data = kpi_to_dict(kpis)
        findings = []
        if (data.get("backhaul_utilization") or 0) > 75:
            findings.append({
                "rule_id": "transport_backhaul",
                "category": "transport",
                "probable_cause": "Backhaul utilization high — N3/F1 transport congestion",
                "confidence": 0.77,
                "evidence": {"backhaul_utilization": data["backhaul_utilization"]},
                "recommended_actions": ["Upgrade transport link", "Enable QoS on N3"],
            })
        if (data.get("transport_loss_rate") or 0) > 0.3:
            findings.append({
                "rule_id": "transport_loss",
                "category": "transport",
                "probable_cause": "Packet loss on transport path",
                "confidence": 0.74,
                "evidence": {"transport_loss_rate": data["transport_loss_rate"]},
                "recommended_actions": ["Check switch/router counters", "Verify MTU and fragmentation"],
            })
        return self._findings_to_result(findings, f"Transport: {len(findings)} finding(s).")


class CoreAgent(BaseAgent):
    name = "core_agent"

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        data = kpi_to_dict(kpis)
        findings = []
        if (data.get("amf_release_rate") or 0) > 0.5:
            findings.append({
                "rule_id": "core_amf_release",
                "category": "core",
                "probable_cause": "AMF-initiated release — check 5GMM cause and subscription",
                "confidence": 0.73,
                "evidence": {"amf_release_rate": data["amf_release_rate"]},
                "recommended_actions": ["Inspect AMF logs", "Verify UE subscription profile"],
            })
        if (data.get("upf_latency_ms") or 0) > 40:
            findings.append({
                "rule_id": "core_upf_load",
                "category": "core",
                "probable_cause": "UPF latency elevated — user-plane processing delay",
                "confidence": 0.8,
                "evidence": {"upf_latency_ms": data["upf_latency_ms"]},
                "recommended_actions": ["Rebalance UPF cluster", "Scale UPF instances"],
            })
        return self._findings_to_result(findings, f"Core: {len(findings)} finding(s).")


class ComplaintAgent(BaseAgent):
    name = "complaint_agent"

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        from tnic.rules import ISSUE_KEYWORDS, detect_issue_type

        issue = detect_issue_type(query)
        findings = [{
            "rule_id": "complaint_triage",
            "category": "complaint",
            "probable_cause": f"Complaint triaged to **{issue}** domain based on text analysis",
            "confidence": 0.6,
            "evidence": {"query_excerpt": query[:120]},
            "recommended_actions": [f"Run {issue} RCA workflow", "Correlate with PM counters for affected cell"],
        }]
        return self._findings_to_result(findings, f"Complaint triaged to {issue}.")


AGENT_REGISTRY: dict[str, BaseAgent] = {
    "handover": HOAgent(),
    "ho": HOAgent(),
    "rlf": RLFAgent(),
    "call_drop": CallDropAgent(),
    "throughput": ThroughputAgent(),
    "rach": RACHAgent(),
    "beamforming": BeamformingAgent(),
    "beam": BeamformingAgent(),
    "latency": LatencyAgent(),
    "pm": PMAgent(),
    "transport": TransportAgent(),
    "core": CoreAgent(),
    "complaint": ComplaintAgent(),
}
