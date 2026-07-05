"""RCA and analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File

from tnic.exceptions import NotFoundError
from tnic.models.schemas import (
    AnalyzeCellRequest,
    AnalyzeRequest,
    CellHealthRequest,
    CellHealthResponse,
    CellProfileResponse,
    GenerateRCARequest,
    KPIInput,
    PMIngestResponse,
    RCAResponse,
)
from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator
from tnic.rag.retriever import get_rag_store
from tnic.rules import detect_issue_type
from tnic.services.health_scoring import cell_health_response, compute_health_score
from tnic.services.pm_ingestion import aggregate_cell_kpis, ingest_pm_csv

router = APIRouter(tags=["analyze"])
_orchestrator = MasterRCAOrchestrator()


def _rag_for_request(request: AnalyzeRequest) -> list[dict[str, str]]:
    if not request.include_rag:
        return []
    return get_rag_store().search(
        request.query or request.complaint_text or request.issue_type or "5G RCA"
    )


def _run_rca(request: AnalyzeRequest) -> RCAResponse:
    return _orchestrator.run(request, rag_context=_rag_for_request(request))


def _analyze_with_issue(request: AnalyzeRequest, issue_type: str) -> RCAResponse:
    request.issue_type = issue_type
    return _run_rca(request)


def _kpi_input_from_generate(req: GenerateRCARequest) -> KPIInput:
    if req.cell_id:
        from tnic.datasets.kpi_service import build_kpi_input

        return build_kpi_input(cell_id=req.cell_id, query=req.query)
    return req.kpis


@router.post("/analyze/rca", response_model=RCAResponse)
def analyze_rca(request: AnalyzeRequest):
    return _run_rca(request)


@router.post("/generate-rca", response_model=RCAResponse)
def generate_rca(request: GenerateRCARequest):
    return _run_rca(
        AnalyzeRequest(
            query=request.query,
            issue_type=request.issue_type,
            kpis=_kpi_input_from_generate(request),
            complaint_text=request.complaint_text,
            include_rag=request.include_rag,
            generate_report=request.generate_report,
        )
    )


@router.post("/analyze-cell", response_model=RCAResponse)
def analyze_cell(request: AnalyzeCellRequest):
    from tnic.datasets.kpi_service import build_kpi_input, list_cell_ids

    cell_id = request.cell_id.upper()
    if cell_id not in list_cell_ids():
        raise NotFoundError(f"Cell not found: {cell_id}")

    issue = request.issue_type or detect_issue_type(request.query or f"cell {cell_id}")
    query = request.query or f"Root cause {issue.replace('_', ' ')} cell {cell_id}"
    kpi = build_kpi_input(cell_id=cell_id, query=query)
    return _run_rca(
        AnalyzeRequest(
            query=query,
            issue_type=issue,
            kpis=kpi,
            include_rag=request.include_rag,
            generate_report=request.generate_report,
        )
    )


@router.get("/cell/{cell_id}", response_model=CellProfileResponse)
def get_cell_profile(cell_id: str):
    from tnic.datasets.kpi_service import compute_cell_kpis, list_cell_ids
    from tnic.services.incidents import load_incidents

    cid = cell_id.upper()
    if cid not in list_cell_ids():
        raise NotFoundError(f"Cell not found: {cid}")

    bundle = compute_cell_kpis(cid)
    health = compute_health_score(bundle.kpis)
    related = [i for i in load_incidents() if str(i.get("cell_id", "")).upper() == cid]

    return CellProfileResponse(
        cell_id=cid,
        kpis=bundle.kpis,
        sources=bundle.sources,
        health_score=health["overall_score"],
        grade=health["grade"],
        dimensions=health["dimensions"],
        alerts=health["alerts"],
        incident_count=len(related),
        related_incidents=related[:5],
    )


@router.post("/analyze/handover", response_model=RCAResponse)
@router.post("/analyze-ho", response_model=RCAResponse)
def analyze_handover(request: AnalyzeRequest):
    return _analyze_with_issue(request, "handover")


@router.post("/analyze/rach", response_model=RCAResponse)
@router.post("/analyze-rach", response_model=RCAResponse)
def analyze_rach(request: AnalyzeRequest):
    return _analyze_with_issue(request, "rach")


@router.post("/analyze/throughput", response_model=RCAResponse)
def analyze_throughput(request: AnalyzeRequest):
    return _analyze_with_issue(request, "throughput")


@router.post("/analyze/call-drop", response_model=RCAResponse)
def analyze_call_drop(request: AnalyzeRequest):
    return _analyze_with_issue(request, "call_drop")


@router.post("/analyze/latency", response_model=RCAResponse)
def analyze_latency(request: AnalyzeRequest):
    return _analyze_with_issue(request, "latency")


@router.post("/analyze/beamforming", response_model=RCAResponse)
def analyze_beamforming(request: AnalyzeRequest):
    return _analyze_with_issue(request, "beamforming")


@router.post("/analyze/vonr", response_model=RCAResponse)
def analyze_vonr(request: AnalyzeRequest):
    return _analyze_with_issue(request, "vonr")


@router.post("/analyze/anr", response_model=RCAResponse)
def analyze_anr(request: AnalyzeRequest):
    return _analyze_with_issue(request, "anr")


@router.post("/analyze/config-audit", response_model=RCAResponse)
def analyze_config_audit(request: AnalyzeRequest):
    return _analyze_with_issue(request, "config_audit")


@router.post("/analyze/gnb-syslog", response_model=RCAResponse)
def analyze_gnb_syslog(request: AnalyzeRequest):
    return _analyze_with_issue(request, "gnb_syslog")


@router.post("/analyze/cell-outage", response_model=RCAResponse)
def analyze_cell_outage(request: AnalyzeRequest):
    return _analyze_with_issue(request, "cell_outage")


@router.post("/analyze/rf-coverage")
def analyze_rf_coverage(request: AnalyzeRequest):
    """3-mile geospatial drive-test analysis with Google Maps artifact."""
    from tnic.agents.rf_coverage_agent import analyze_rf_coverage

    return analyze_rf_coverage(
        query=request.query or "RF coverage drive test 3 mile radius",
        radius_miles=3.0,
    )


@router.post("/health-score/cell", response_model=CellHealthResponse)
def cell_health(request: CellHealthRequest):
    data = cell_health_response(request.cell_id, request.kpis.model_dump(exclude_none=True))
    return CellHealthResponse(**data)


@router.post("/pm/ingest", response_model=PMIngestResponse)
async def pm_ingest(file: UploadFile = File(...)):
    import tempfile
    from pathlib import Path

    suffix = Path(file.filename or "pm.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    result = ingest_pm_csv(path)
    return PMIngestResponse(**result)


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
