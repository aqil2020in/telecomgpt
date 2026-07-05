"""Upload and dynamic ingestion API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from tnic.models.upload_models import FileClassification, SchemaInference, UploadIngestResult, UploadRCAResult
from tnic.services.dynamic_rca import ingest_and_run_rca, run_dynamic_rca
from tnic.services.event_repository import (
    get_stored_file_path,
    list_uploads,
    load_events,
    load_manifest,
)
from tnic.services.ingest_pipeline import ingest_uploaded_bytes

router = APIRouter(tags=["upload"])

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".txt", ".log", ".pcap", ".zip"}


@router.post("/upload", response_model=UploadIngestResult)
async def upload_file(file: UploadFile = File(...)):
    """Upload a telecom file — auto classify, parse, normalize, store."""
    filename = file.filename or "upload.bin"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        return UploadIngestResult(
            ok=False,
            upload_id="",
            filename=filename,
            classification=FileClassification(file_type="UNKNOWN", confidence=0.0),
            schema_info=SchemaInference(format="unknown"),
            message=f"Unsupported extension {suffix}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    content = await file.read()
    return ingest_uploaded_bytes(filename, content)


@router.post("/upload/rca", response_model=UploadRCAResult)
async def upload_and_rca(
    file: UploadFile = File(...),
    cell_id: str | None = Form(None),
    ue_id: str | None = Form(None),
    query: str = Form(""),
    generate_report: bool = Form(False),
):
    """Upload file and immediately run dynamic RCA."""
    content = await file.read()
    return ingest_and_run_rca(
        file.filename or "upload.csv",
        content,
        cell_id=cell_id,
        ue_id=ue_id,
        query=query,
        generate_report=generate_report,
    )


@router.get("/uploads")
def list_all_uploads(limit: int = 50):
    uploads = list_uploads(limit=limit)
    return {"ok": True, "count": len(uploads), "uploads": [u.model_dump() for u in uploads]}


@router.get("/upload/{upload_id}")
def get_upload(upload_id: str):
    manifest = load_manifest(upload_id)
    if not manifest:
        return {"ok": False, "error": f"Upload not found: {upload_id}"}
    events = load_events(upload_id)
    failures = [e for e in events if e.is_failure()]
    stored = get_stored_file_path(upload_id)
    return {
        "ok": True,
        "manifest": manifest.model_dump(),
        "stored_file": str(stored) if stored else None,
        "event_count": len(events),
        "failure_count": len(failures),
        "events_preview": [e.to_dict() for e in events[:20]],
        "failures_preview": [e.to_dict() for e in failures[:20]],
    }


@router.get("/upload/{upload_id}/events")
def get_upload_events(
    upload_id: str,
    cell_id: str | None = None,
    ue_id: str | None = None,
    failures_only: bool = False,
    limit: int = 200,
):
    events = load_events(upload_id, cell_id=cell_id, ue_id=ue_id, failures_only=failures_only)
    return {
        "ok": True,
        "upload_id": upload_id,
        "count": len(events),
        "events": [e.to_dict() for e in events[:limit]],
    }


@router.post("/upload/{upload_id}/rca", response_model=UploadRCAResult)
def rca_from_upload(
    upload_id: str,
    cell_id: str | None = None,
    ue_id: str | None = None,
    query: str = "",
    workflow: str = "historical",
    generate_report: bool = False,
):
    """Run RCA on a previously uploaded file (historical / single cell / single UE)."""
    return run_dynamic_rca(
        upload_id,
        cell_id=cell_id,
        ue_id=ue_id,
        query=query,
        workflow=workflow,
        generate_report=generate_report,
    )
