"""UE Protocol Correlation Agent — UE-side trace RCA."""

from __future__ import annotations

import re
from typing import Any

from tnic.agents.base import BaseAgent, kpi_to_dict
from tnic.models.schemas import AgentResult
from tnic.models.ue_rca_result import UERcaResult
from tnic.parsers.ue_trace_parser import UETraceParser
from tnic.services.ue_correlation_service import correlate_cell_ue_failures


class UEProtocolAgent(BaseAgent):
    name = "ue_protocol_agent"
    issue_types = ("ue_protocol", "ue_trace", "protocol_trace")

    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        data = kpi_to_dict(kpis)
        cell_id = str(data.get("cell_id") or self._cell_from_query(query) or "XYZ401").upper()
        ue_id = data.get("ue_id") or self._ue_from_query(query)

        # Prefer normalized upload events when present
        upload_failures = data.get("ue_trace_failures") or []
        if upload_failures and data.get("upload_id"):
            findings = self._findings_from_upload_failures(upload_failures, cell_id, data)
            if findings:
                top = max(findings, key=lambda f: f.get("confidence", 0))
                summary = (
                    f"UE Protocol Agent (upload): {len(findings)} failure(s) on {cell_id}. "
                    f"Top: {top.get('probable_cause', '')[:80]}"
                )
                return self._findings_to_result(findings, summary)

        results = correlate_cell_ue_failures(cell_id, ue_id=ue_id, cell_kpis=data)
        if not results:
            summary = parser_summary(cell_id)
            return self._findings_to_result([], f"No UE protocol failures in trace for {cell_id}. {summary}")

        findings = [r.to_finding_dict() for r in results]
        top = max(results, key=lambda r: r.confidence)
        summary = (
            f"UE Protocol Agent: {len(results)} failure(s) on {cell_id}. "
            f"Top: {top.issue} @ {top.failure_stage} (confidence {int(top.confidence * 100)}%)"
        )
        return self._findings_to_result(findings, summary)

    def analyze_ue(self, cell_id: str, ue_id: str | None = None, kpis: dict | None = None) -> list[UERcaResult]:
        return correlate_cell_ue_failures(cell_id, ue_id=ue_id, cell_kpis=kpis)

    @staticmethod
    def _findings_from_upload_failures(
        failures: list[dict[str, Any]],
        cell_id: str,
        kpis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        from tnic.services.ue_correlation_service import compute_ue_confidence

        findings: list[dict[str, Any]] = []
        has_gnb = bool(kpis.get("syslog_event_count") or kpis.get("syslog_signatures"))
        has_pm = bool(kpis.get("ho_success_rate") or kpis.get("rach_success_rate"))
        has_rf = kpis.get("ss_rsrp") is not None
        has_transport = (kpis.get("transport_alarm_count") or 0) > 0
        conf, factors = compute_ue_confidence(
            has_ue=True, has_gnb=has_gnb, has_pm=has_pm, has_rf=has_rf, has_transport=has_transport,
        )
        for i, f in enumerate(failures[:20]):
            cause = f.get("cause") or f.get("event", "UE failure")
            findings.append({
                "rule_id": f"ue_upload_{i}",
                "category": "ue_protocol",
                "probable_cause": f"[Upload UE Trace] {cause} — UE {f.get('ue_id', '?')}",
                "confidence": conf,
                "evidence": {
                    "ue_id": f.get("ue_id"),
                    "cell_id": cell_id,
                    "event": f.get("event"),
                    "source": "upload_normalized_events",
                    "confidence_factors": factors,
                },
                "recommended_actions": ["Correlate upload trace with gNB syslog and PM counters"],
            })
        return findings

    @staticmethod
    def _cell_from_query(query: str) -> str | None:
        m = re.search(r"\b(XYZ\d{3,4}|432\d{2})\b", query, re.I)
        return m.group(1).upper() if m else None

    @staticmethod
    def _ue_from_query(query: str) -> str | None:
        m = re.search(r"\b(UE\d+)\b", query, re.I)
        return m.group(1).upper() if m else None


def parser_summary(cell_id: str) -> str:
    try:
        s = UETraceParser().cell_summary(cell_id)
        return f"Trace rows: {s['failure_count']} failures across {s['ue_count']} UEs."
    except Exception:
        return "UE protocol trace dataset not loaded."


UEProtocolAgent = UEProtocolAgent
