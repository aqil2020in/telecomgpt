"""Pydantic models for telecom RCA datasets."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PMCounterRow(BaseModel):
    timestamp: datetime
    cell_id: str
    ho_attempt: int = Field(ge=0)
    rach_attempt: int = Field(ge=0)
    dl_tp: float = Field(ge=0)
    ul_tp: float = Field(ge=0)
    cqi: float = Field(ge=0, le=15)
    ho_success: int = Field(ge=0)
    rach_success: int = Field(ge=0)


class HandoverEventRow(BaseModel):
    ue_id: str
    cell_id: str
    rsrp: float
    sinr: float
    failure_type: str


class RLFEventRow(BaseModel):
    ue_id: str
    cell_id: str
    rsrp: float
    sinr: float
    cause: str


class RachEventRow(BaseModel):
    ue_id: str
    cell_id: str
    msg_failure: str


class CallDropEventRow(BaseModel):
    ue_id: str
    cell_id: str
    drop_type: str


class ThroughputMetricRow(BaseModel):
    cell_id: str
    cqi: float = Field(ge=0, le=15)
    prb_util: float = Field(ge=0, le=100)
    dl_tp: float = Field(ge=0)
    issue: str


class ValidationIssue(BaseModel):
    dataset: str
    severity: str
    message: str
    row: int | None = None


class DatasetValidationResult(BaseModel):
    dataset: str
    ok: bool
    row_count: int
    issues: list[ValidationIssue] = Field(default_factory=list)


class DatasetSummary(BaseModel):
    name: str
    file: str
    row_count: int
    cell_count: int
    cells: list[str]
    columns: list[str]
    time_range: dict[str, str] | None = None
    category_counts: dict[str, int] = Field(default_factory=dict)
    numeric_stats: dict[str, dict[str, float]] = Field(default_factory=dict)


class CellKPIs(BaseModel):
    cell_id: str
    kpis: dict[str, Any]
    sources: list[str] = Field(default_factory=list)
    health_score: float | None = None


class ClusterKPISummary(BaseModel):
    cell_count: int
    cells: dict[str, CellKPIs]
    worst_cells: list[str] = Field(default_factory=list)
