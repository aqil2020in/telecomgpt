"""Specialist agents — thin wrappers over rule engines."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent, kpi_to_dict
from app.models.schemas import AgentResult
from app.rules import RULE_ENGINES
from app.rules.beamforming_rules import BEAMFORMING_RULE_ENGINE
from app.rules.call_drop_rules import CALL_DROP_RULE_ENGINE
from app.rules.ho_rules import HO_RULE_ENGINE
from app.rules.latency_rules import LATENCY_RULE_ENGINE
from app.rules.rach_rules import RACH_RULE_ENGINE
from app.rules.rlf_rules import RLF_RULE_ENGINE
from app.rules.throughput_rules import THROUGHPUT_RULE_ENGINE


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


class HOAgent(_RuleAgent):
    def __init__(self):
        super().__init__("ho_agent", HO_RULE_ENGINE)


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
        from app.services.pm_ingestion import validate_pm_kpis

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
        from app.rules import ISSUE_KEYWORDS, detect_issue_type

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
