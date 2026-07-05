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
