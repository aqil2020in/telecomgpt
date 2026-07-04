"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str = "1.0.0"
    postgres: str
    chroma: str
    openai: str


class KPIInput(BaseModel):
    cell_id: str | None = None
    pci: int | None = None
    ss_rsrp: float | None = None
    ss_rsrq: float | None = None
    ss_sinr: float | None = None
    cqi: float | None = None
    bler: float | None = None
    mcs: float | None = None
    ri: float | None = None
    throughput_mbps: float | None = None
    ho_success_rate: float | None = None
    ho_prep_fail_rate: float | None = None
    rach_success_rate: float | None = None
    rlf_rate: float | None = None
    call_drop_rate: float | None = None
    beam_failure_ratio: float | None = None
    latency_ms: float | None = None
    upf_latency_ms: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AnalyzeRequest(BaseModel):
    query: str = ""
    issue_type: str | None = None
    kpis: KPIInput = Field(default_factory=KPIInput)
    complaint_text: str | None = None
    include_rag: bool = True
    generate_report: bool = False


class RuleFinding(BaseModel):
    rule_id: str
    category: str
    probable_cause: str
    confidence: float
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommended_actions: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent: str
    findings: list[RuleFinding] = Field(default_factory=list)
    summary: str = ""
    health_score: float | None = None


class KnowledgeGraphNode(BaseModel):
    id: str
    type: str
    label: str


class KnowledgeGraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class KnowledgeGraph(BaseModel):
    nodes: list[KnowledgeGraphNode] = Field(default_factory=list)
    edges: list[KnowledgeGraphEdge] = Field(default_factory=list)


class RCANarrativeReport(BaseModel):
    """Structured OpenAI RCA narrator output."""

    executive_summary: str
    root_cause: str
    evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "template"

    def to_markdown(self) -> str:
        lines = [
            "## Executive Summary",
            self.executive_summary,
            "",
            "## Root Cause",
            self.root_cause,
            "",
            "## Evidence",
        ]
        for item in self.evidence:
            lines.append(f"- {item}")
        lines.extend(["", "## Recommendations"])
        for i, rec in enumerate(self.recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.extend([
            "",
            "## Confidence",
            f"**{int(round(self.confidence * 100))}%** overall RCA confidence",
        ])
        return "\n".join(lines)


class RCAResponse(BaseModel):
    ok: bool = True
    issue_type: str
    query: str
    agents_run: list[str]
    findings: list[RuleFinding]
    probable_root_causes: list[dict[str, Any]]
    recommended_actions: list[str]
    validation_checklist: list[str]
    health_score: float | None = None
    knowledge_graph: KnowledgeGraph | None = None
    rag_context: list[dict[str, str]] = Field(default_factory=list)
    narrative_report: str | None = None
    narrative_structured: RCANarrativeReport | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CellHealthRequest(BaseModel):
    cell_id: str
    kpis: KPIInput = Field(default_factory=KPIInput)


class CellHealthResponse(BaseModel):
    cell_id: str
    overall_score: float
    grade: str
    dimensions: dict[str, float]
    alerts: list[str]


class PMIngestResponse(BaseModel):
    ok: bool
    rows_ingested: int
    cells: list[str]
    kpi_summary: dict[str, Any]
    validation_issues: list[str] = Field(default_factory=list)


class GenerateRCARequest(BaseModel):
    query: str = Field(..., min_length=1)
    cell_id: str | None = None
    issue_type: str | None = None
    complaint_text: str | None = None
    include_rag: bool = True
    generate_report: bool = True
    kpis: KPIInput = Field(default_factory=KPIInput)


class AnalyzeCellRequest(BaseModel):
    cell_id: str = Field(..., min_length=3)
    issue_type: str | None = None
    query: str | None = None
    include_rag: bool = True
    generate_report: bool = False


class CellProfileResponse(BaseModel):
    ok: bool = True
    cell_id: str
    kpis: dict[str, Any]
    sources: list[str] = Field(default_factory=list)
    health_score: float
    grade: str
    dimensions: dict[str, float]
    alerts: list[str] = Field(default_factory=list)
    incident_count: int = 0
    related_incidents: list[dict[str, Any]] = Field(default_factory=list)
