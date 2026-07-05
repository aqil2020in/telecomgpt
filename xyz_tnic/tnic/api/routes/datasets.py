"""Telecom dataset API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from tnic.datasets.kpi_service import compute_cell_kpis, compute_cluster_kpis, list_cell_ids
from tnic.datasets.summary import summarize_all, summarize_dataset
from tnic.datasets.validation import validate_all, validate_dataset

router = APIRouter(tags=["datasets"])


@router.get("/datasets/assurance/ingest-all")
def assurance_ingest_all():
    """Ingest and validate all core assurance datasets."""
    from tnic.services.assurance_ingestion import ingest_all_assurance

    results = ingest_all_assurance()
    return {
        "ok": all(r.ok for r in results.values()),
        "datasets": {k: v.model_dump() for k, v in results.items()},
    }


@router.get("/datasets/assurance/kpis/{cell_id}")
def assurance_cell_kpis(cell_id: str):
    """Assurance-only KPI aggregation for a cell."""
    from tnic.services.assurance_ingestion import aggregate_assurance_kpis

    kpis = aggregate_assurance_kpis(cell_id.upper())
    return {"ok": True, "cell_id": cell_id.upper(), "kpis": kpis}


@router.get("/datasets/assurance/evidence/{cell_id}")
def assurance_cell_evidence(cell_id: str):
    """Build assurance evidence findings for Master RCA preview."""
    from tnic.services.assurance_evidence import assurance_recommendation_summary, build_assurance_evidence

    findings = build_assurance_evidence(cell_id.upper())
    summary = assurance_recommendation_summary(findings)
    return {
        "ok": True,
        "cell_id": cell_id.upper(),
        "finding_count": len(findings),
        "summary": summary,
        "findings": [f.model_dump() for f in findings],
    }


@router.get("/datasets/ue-trace/{cell_id}")
def ue_trace_cell_summary(cell_id: str, ue_id: str | None = None):
    """UE protocol trace summary and RCA results for a cell."""
    from tnic.parsers.ue_trace_parser import UETraceParser
    from tnic.services.ue_correlation_service import correlate_cell_ue_failures

    cid = cell_id.upper()
    parser = UETraceParser()
    summary = parser.cell_summary(cid)
    results = correlate_cell_ue_failures(cid, ue_id=ue_id.upper() if ue_id else None)
    return {
        "ok": True,
        "cell_id": cid,
        "ue_id": ue_id.upper() if ue_id else None,
        "summary": summary,
        "results": [r.model_dump() for r in results],
    }


@router.get("/datasets/summary")
def datasets_summary():
    return summarize_all()


@router.get("/datasets/validate-all")
def datasets_validate_all():
    results = validate_all()
    return {
        "ok": all(r.ok for r in results),
        "results": [r.model_dump() for r in results],
    }


@router.get("/datasets/cells")
def datasets_cells():
    cells = list_cell_ids()
    return {"ok": True, "cells": cells, "count": len(cells)}


@router.get("/datasets/kpis")
def all_cell_kpis(limit: int = Query(20, ge=1, le=100)):
    cluster = compute_cluster_kpis()
    cells = list(cluster.cells.items())[:limit]
    return {
        "ok": True,
        "cell_count": cluster.cell_count,
        "worst_cells": cluster.worst_cells,
        "cells": {cid: bundle.model_dump() for cid, bundle in cells},
    }


@router.get("/datasets/kpis/{cell_id}")
def cell_kpis(cell_id: str):
    bundle = compute_cell_kpis(cell_id.upper())
    return {"ok": True, "cell": bundle.model_dump()}


@router.get("/datasets/{name}/summary")
def dataset_summary(name: str):
    return {"ok": True, "summary": summarize_dataset(name).model_dump()}


@router.get("/datasets/{name}/validate")
def dataset_validate(name: str):
    result = validate_dataset(name)
    return {"ok": result.ok, "validation": result.model_dump()}
