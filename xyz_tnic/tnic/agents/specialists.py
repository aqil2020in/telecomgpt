"""Specialist agents — thin wrappers over rule engines."""

from __future__ import annotations

from typing import Any

from tnic.agents.base import BaseAgent, kpi_to_dict
from tnic.agents.rf_coverage_agent import RFCoverageAgent as _RFCoverageCore
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


class PMAgent(_RuleAgent):
    def __init__(self):
        from tnic.rules.pm_validation_rules import PM_VALIDATION_RULE_ENGINE
        super().__init__("pm_agent", PM_VALIDATION_RULE_ENGINE)


class TransportAgent(_RuleAgent):
    def __init__(self):
        from tnic.rules.transport_rules import TRANSPORT_RULE_ENGINE
        super().__init__("transport_agent", TRANSPORT_RULE_ENGINE)


class CoreAgent(_RuleAgent):
    def __init__(self):
        from tnic.rules.core_rules import CORE_RULE_ENGINE
        super().__init__("core_agent", CORE_RULE_ENGINE)


class AlarmAgent(_RuleAgent):
    def __init__(self):
        from tnic.rules.alarm_rules import ALARM_RULE_ENGINE
        super().__init__("alarm_agent", ALARM_RULE_ENGINE)


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


class RFCoverageAgent(BaseAgent):
    name = "rf_coverage_agent"

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        data = kpi_to_dict(kpis)
        from tnic.rules.coverage_rules import COVERAGE_RULE_ENGINE

        pm_findings = COVERAGE_RULE_ENGINE.evaluate(data)
        summary = _RFCoverageCore().analyze(data, query=query)
        if summary.get("primary_issue") == "No Data":
            if pm_findings:
                return self._findings_to_result(
                    pm_findings,
                    f"PM coverage rules: {len(pm_findings)} finding(s).",
                )
            return self._findings_to_result([], f"No geospatial data for {data.get('cell_id') or 'requested cell'}.")

        findings = list(pm_findings)
        findings.append({
            "rule_id": "rf_coverage_primary",
            "category": "rf_coverage",
            "probable_cause": (
                f"{summary['primary_issue']} on {summary['cell_id']} "
                f"(score {summary['coverage_score']}, confidence {int(float(summary['confidence']) * 100)}%)"
            ),
            "confidence": float(summary["confidence"]),
            "evidence": {
                "cell_id": summary["cell_id"],
                "coverage_score": summary["coverage_score"],
                "secondary_issue": summary.get("secondary_issue"),
                "metrics": summary.get("metrics", {}),
                "issue_counts": summary.get("issue_counts", {}),
                "impacts": summary.get("impacts", []),
            },
            "recommended_actions": [summary.get("recommendation", "Re-drive 3 mi cluster")],
        })
        if summary.get("secondary_issue"):
            findings.append({
                "rule_id": "rf_coverage_secondary",
                "category": "rf_coverage",
                "probable_cause": f"Secondary: {summary['secondary_issue']}",
                "confidence": float(summary["confidence"]) - 0.05,
                "evidence": {"cell_id": summary["cell_id"]},
                "recommended_actions": ["Address secondary beam/RF issue after primary coverage fix"],
            })
        return self._findings_to_result(
            findings,
            f"RF coverage on {summary['cell_id']}: {summary['primary_issue']} "
            f"(score {summary['coverage_score']}).",
        )


class GNBSyslogAgent(BaseAgent):
    name = "gnb_syslog_agent"

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        data = kpi_to_dict(kpis)
        data["query"] = query
        data["syslog_text"] = data.get("syslog_text") or query
        from tnic.rules.gnb_syslog_rules import GNB_SYSLOG_RULE_ENGINE
        findings = GNB_SYSLOG_RULE_ENGINE.evaluate(data)
        return self._findings_to_result(findings, f"Syslog analysis: {len(findings)} signature(s) matched.")


class ConfigAuditAgent(BaseAgent):
    name = "config_audit_agent"

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        from tnic.rules.config_audit_rules import CONFIG_AUDIT_RULE_ENGINE
        findings = CONFIG_AUDIT_RULE_ENGINE.evaluate(kpi_to_dict(kpis))
        return self._findings_to_result(findings, f"Config audit: {len(findings)} parameter drift(s).")


class ANRAgent(_RuleAgent):
    def __init__(self):
        from tnic.rules.anr_rules import ANR_RULE_ENGINE
        super().__init__("anr_agent", ANR_RULE_ENGINE)


class VoNRAgent(_RuleAgent):
    def __init__(self):
        from tnic.rules.vonr_rules import VONR_RULE_ENGINE
        super().__init__("vonr_agent", VONR_RULE_ENGINE)


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
    "rf_coverage": RFCoverageAgent(),
    "coverage": RFCoverageAgent(),
    "vonr": VoNRAgent(),
    "anr": ANRAgent(),
    "config_audit": ConfigAuditAgent(),
    "gnb_syslog": GNBSyslogAgent(),
    "alarm": AlarmAgent(),
}
