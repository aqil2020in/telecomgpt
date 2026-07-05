"""Upload and ingestion result models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tnic.models.normalized_event import NormalizedEvent


class FileClassification(BaseModel):
    file_type: str
    confidence: float
    signals: list[str] = Field(default_factory=list)
    protocol_hints: list[str] = Field(default_factory=list)


class SchemaInference(BaseModel):
    format: str = "tabular"
    columns: list[str] = Field(default_factory=list)
    column_map: dict[str, str] = Field(default_factory=dict)
    row_count: int = 0
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class UploadIngestResult(BaseModel):
    ok: bool
    upload_id: str
    filename: str
    stored_path: str = ""
    classification: FileClassification
    schema_info: SchemaInference = Field(default_factory=SchemaInference)
    cell_ids: list[str] = Field(default_factory=list)
    ue_ids: list[str] = Field(default_factory=list)
    event_count: int = 0
    failure_count: int = 0
    events_preview: list[dict[str, Any]] = Field(default_factory=list)
    failures_preview: list[dict[str, Any]] = Field(default_factory=list)
    rca_ready: bool = False
    message: str = ""


class UploadManifest(BaseModel):
    upload_id: str
    filename: str
    original_filename: str
    file_type: str
    classification_confidence: float
    uploaded_at: str
    stored_path: str
    cell_ids: list[str] = Field(default_factory=list)
    ue_ids: list[str] = Field(default_factory=list)
    event_count: int = 0
    failure_count: int = 0
    domains: list[str] = Field(default_factory=list)


class UploadRCAResult(BaseModel):
    upload_id: str
    cell_id: str | None = None
    ue_id: str | None = None
    workflow: str = "new_upload"
    events_used: int = 0
    ingest: UploadIngestResult | None = None
    rca: dict[str, Any] = Field(default_factory=dict)
