"""Dynamic RCA workflow — run existing agents on uploaded normalized events."""

from __future__ import annotations

from typing import Any

from tnic.datasets.kpi_service import compute_cell_kpis, extract_cell_id, pick_worst_cell
from tnic.models.schemas import AnalyzeRequest, KPIInput
from tnic.models.upload_models import UploadIngestResult, UploadRCAResult
from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator
from tnic.services.event_repository import load_events, load_manifest
from tnic.services.events_kpi_bridge import kpis_from_events, merge_kpis
from tnic.services.ingest_pipeline import ingest_uploaded_bytes


def _resolve_cell_id(events, cell_id: str | None, query: str) -> str:
    if cell_id:
        return cell_id.upper()
    from_events = next((e.cell_id for e in events if e.cell_id), None)
    if from_events:
        return from_events
    return extract_cell_id(query) or pick_worst_cell()


def run_dynamic_rca(
    upload_id: str,
    *,
    cell_id: str | None = None,
    ue_id: str | None = None,
    query: str = "",
    workflow: str = "new_upload",
    include_bundled_kpis: bool = True,
    generate_report: bool = False,
) -> UploadRCAResult:
    """Run Master RCA using normalized events from an upload."""
    manifest = load_manifest(upload_id)
    if not manifest:
        raise ValueError(f"Upload not found: {upload_id}")

    events = load_events(upload_id, cell_id=cell_id, ue_id=ue_id)
    if not events:
        events = load_events(upload_id)

    cid = _resolve_cell_id(events, cell_id, query)
    event_kpis = kpis_from_events(events, cid)

    merged = dict(event_kpis)
    if include_bundled_kpis and cid:
        try:
            bundled = compute_cell_kpis(cid).kpis
            merged = merge_kpis(bundled, event_kpis)
        except Exception:
            pass

    merged["cell_id"] = cid
    merged["upload_id"] = upload_id
    if ue_id:
        merged["ue_id"] = ue_id.upper()

    q = query or _default_query(workflow, manifest, cid, ue_id, events)

    fields = KPIInput.model_fields
    payload = {k: v for k, v in merged.items() if k in fields and v is not None}
    payload["cell_id"] = cid
    extra = {k: v for k, v in merged.items() if k not in fields}
    if extra:
        payload["extra"] = extra

    orch = MasterRCAOrchestrator()
    rca = orch.run(
        AnalyzeRequest(
            query=q,
            kpis=KPIInput(**payload),
            include_rag=False,
            generate_report=generate_report,
        )
    )

    return UploadRCAResult(
        upload_id=upload_id,
        cell_id=cid,
        ue_id=ue_id,
        workflow=workflow,
        events_used=len(events),
        rca=rca.model_dump(),
    )


def ingest_and_run_rca(
    filename: str,
    content: bytes,
    *,
    cell_id: str | None = None,
    ue_id: str | None = None,
    query: str = "",
    generate_report: bool = False,
) -> UploadRCAResult:
    """Upload → classify → normalize → correlate → RCA in one call."""
    ingest = ingest_uploaded_bytes(filename, content)
    if not ingest.ok:
        return UploadRCAResult(
            upload_id=ingest.upload_id,
            workflow="new_upload",
            ingest=ingest,
            rca={"ok": False, "error": ingest.message},
        )
    result = run_dynamic_rca(
        ingest.upload_id,
        cell_id=cell_id or (ingest.cell_ids[0] if ingest.cell_ids else None),
        ue_id=ue_id,
        query=query,
        generate_report=generate_report,
    )
    result.ingest = ingest
    return result


def _default_query(
    workflow: str,
    manifest: Any,
    cell_id: str,
    ue_id: str | None,
    events: list,
) -> str:
    fails = sum(1 for e in events if e.is_failure())
    base = f"{workflow.replace('_', ' ')} RCA"
    if manifest.file_type == "UE_PROTOCOL_TRACE":
        base = f"UE protocol trace failure analysis cell {cell_id}"
    elif manifest.file_type == "GNB_SYSLOG":
        base = f"gNB syslog correlation cell {cell_id}"
    elif manifest.file_type == "RF_MEASUREMENT":
        base = f"RF coverage analysis cell {cell_id}"
    elif fails:
        base = f"Root cause analysis {fails} failures cell {cell_id}"
    else:
        base = f"Telecom RCA cell {cell_id}"
    if ue_id:
        base += f" UE {ue_id}"
    return base
