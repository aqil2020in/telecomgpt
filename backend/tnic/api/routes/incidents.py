"""Incident dataset endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from tnic.services.incidents import get_incident, incidents_by_issue, load_incidents

router = APIRouter(tags=["incidents"])


@router.get("/incidents")
def list_incidents(issue_type: str | None = Query(None)):
    rows = incidents_by_issue(issue_type) if issue_type else load_incidents()
    return {"ok": True, "count": len(rows), "incidents": rows}


@router.get("/incidents/{incident_id}")
def incident_detail(incident_id: str):
    return {"ok": True, "incident": get_incident(incident_id)}
