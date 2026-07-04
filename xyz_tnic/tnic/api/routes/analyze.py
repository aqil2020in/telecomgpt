"""RCA and analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File

from tnic.models.schemas import AnalyzeRequest, CellHealthRequest, CellHealthResponse, KPIInput, RCAResponse
from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator
from tnic.rag.retriever import get_rag_store
from tnic.services.health_scoring import cell_health_response
from tnic.services.pm_ingestion import aggregate_cell_kpis, ingest_pm_csv

router = APIRouter(tags=["analyze"])
_orchestrator = MasterRCAOrchestrator()


@router.post("/analyze/rca", response_model=RCAResponse)
def analyze_rca(request: AnalyzeRequest):
    rag = []
    if request.include_rag:
        rag = get_rag_store().search(request.query or request.complaint_text or request.issue_type or "5G RCA")
    return _orchestrator.run(request, rag_context=rag)


@router.post("/analyze/handover", response_model=RCAResponse)
def analyze_handover(request: AnalyzeRequest):
    request.issue_type = "handover"
    return analyze_rca(request)


@router.post("/analyze/rach", response_model=RCAResponse)
def analyze_rach(request: AnalyzeRequest):
    request.issue_type = "rach"
    return analyze_rca(request)


@router.post("/analyze/throughput", response_model=RCAResponse)
def analyze_throughput(request: AnalyzeRequest):
    request.issue_type = "throughput"
    return analyze_rca(request)


@router.post("/analyze/call-drop", response_model=RCAResponse)
def analyze_call_drop(request: AnalyzeRequest):
    request.issue_type = "call_drop"
    return analyze_rca(request)


@router.post("/analyze/latency", response_model=RCAResponse)
def analyze_latency(request: AnalyzeRequest):
    request.issue_type = "latency"
    return analyze_rca(request)


@router.post("/analyze/beamforming", response_model=RCAResponse)
def analyze_beamforming(request: AnalyzeRequest):
    request.issue_type = "beamforming"
    return analyze_rca(request)


@router.post("/health-score/cell", response_model=CellHealthResponse)
def cell_health(request: CellHealthRequest):
    data = cell_health_response(request.cell_id, request.kpis.model_dump(exclude_none=True))
    return CellHealthResponse(**data)


@router.post("/pm/ingest")
async def pm_ingest(file: UploadFile = File(...)):
    import tempfile
    from pathlib import Path

    suffix = Path(file.filename or "pm.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    return ingest_pm_csv(path)


@router.get("/pm/cell/{cell_id}/kpis")
def pm_cell_kpis(cell_id: str):
    from tnic.config import get_settings
    data_dir = get_settings().data_dir
    for name in ("pm_counters.csv", "samples/pm_counters_sample.csv"):
        sample = data_dir / name
        if sample.exists():
            agg = aggregate_cell_kpis(sample)
            return {"ok": True, "cell_id": cell_id, "kpis": agg.get(cell_id, {})}
    return {"ok": False, "error": "PM counters file not found"}
