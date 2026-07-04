"""Telecom dataset API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from tnic.datasets.kpi_service import compute_cell_kpis, compute_cluster_kpis, list_cell_ids
from tnic.datasets.summary import summarize_all, summarize_dataset
from tnic.datasets.validation import validate_all, validate_dataset

router = APIRouter(tags=["datasets"])


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
