"""Upload ingestion pipeline — classify, infer schema, normalize, store."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tnic.models.upload_models import FileClassification, SchemaInference, UploadIngestResult, UploadManifest
from tnic.services.event_repository import (
    create_upload_dir,
    load_events,
    save_events,
    save_manifest,
    save_upload_file,
)
from tnic.services.normalization_engine import normalize_uploaded_file, summarize_events


def ingest_uploaded_bytes(filename: str, content: bytes) -> UploadIngestResult:
    """Full upload → classify → normalize → store pipeline."""
    upload_id, folder = create_upload_dir(filename)
    stored = save_upload_file(upload_id, filename, content)

    try:
        events, classification, schema = normalize_uploaded_file(stored)
    except Exception as exc:
        return UploadIngestResult(
            ok=False,
            upload_id=upload_id,
            filename=filename,
            stored_path=str(stored),
            classification=FileClassification(file_type="UNKNOWN", confidence=0.0),
            schema_info=SchemaInference(format="unknown"),
            message=f"Ingestion failed: {exc}",
        )

    save_events(upload_id, events)
    summary = summarize_events(events)

    manifest = UploadManifest(
        upload_id=upload_id,
        filename=Path(filename).name,
        original_filename=filename,
        file_type=classification.file_type,
        classification_confidence=classification.confidence,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        stored_path=str(stored),
        cell_ids=summary["cell_ids"],
        ue_ids=summary["ue_ids"],
        event_count=summary["event_count"],
        failure_count=summary["failure_count"],
        domains=summary["domains"],
    )
    save_manifest(upload_id, manifest)

    return UploadIngestResult(
        ok=True,
        upload_id=upload_id,
        filename=filename,
        stored_path=str(stored),
        classification=classification,
        schema_info=schema,
        cell_ids=summary["cell_ids"],
        ue_ids=summary["ue_ids"],
        event_count=summary["event_count"],
        failure_count=summary["failure_count"],
        events_preview=summary["events_preview"],
        failures_preview=summary["failures_preview"],
        rca_ready=summary["event_count"] > 0,
        message=f"Ingested {summary['event_count']} events ({summary['failure_count']} failures)",
    )


def ingest_uploaded_file(path: str | Path) -> UploadIngestResult:
    p = Path(path)
    return ingest_uploaded_bytes(p.name, p.read_bytes())
