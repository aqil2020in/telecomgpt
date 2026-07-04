"""RF Coverage API routes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["coverage"])

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


class AnalyzeCoverageRequest(BaseModel):
    cell_id: str = "XYZ401"
    query: str = ""
    radius_miles: float = 3.0
    write_outputs: bool = True


def _agent():
    from agents.rf_coverage_agent import RFCoverageAgent
    return RFCoverageAgent()


@router.post("/analyze-coverage")
def analyze_coverage(request: AnalyzeCoverageRequest):
    agent = _agent()
    summary = agent.analyze_cell(request.cell_id)
    result = summary.to_json_record()
    result["radius_miles"] = request.radius_miles
    if request.write_outputs:
        result["coverage_summary_path"] = str(agent.generate_coverage_summary_json())
        result["coverage_hotspots_path"] = str(agent.generate_coverage_hotspots_csv())
    return {"ok": True, **result}


@router.get("/coverage-summary")
def coverage_summary(cell_id: str | None = Query(None)):
    from agents.rf_coverage_agent import get_coverage_summary
    data = get_coverage_summary(cell_id)
    return {"ok": True, "data": data}


@router.get("/coverage-hotspots")
def coverage_hotspots(
    cell_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=5000),
):
    from agents.rf_coverage_agent import get_coverage_hotspots
    rows = get_coverage_hotspots(cell_id)[:limit]
    return {"ok": True, "count": len(rows), "hotspots": rows}
