"""Telecom incident dataset loader."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from tnic.config import get_settings
from tnic.exceptions import NotFoundError


def incidents_path() -> Path:
    p = get_settings().data_dir / "incidents.csv"
    if not p.exists():
        raise NotFoundError(f"Incidents dataset not found: {p}")
    return p


@lru_cache
def load_incidents() -> list[dict[str, Any]]:
    path = incidents_path()
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_incident(incident_id: str) -> dict[str, Any]:
    for row in load_incidents():
        if row.get("incident_id") == incident_id:
            return row
    raise NotFoundError(f"Incident not found: {incident_id}")


def incidents_by_issue(issue_type: str) -> list[dict[str, Any]]:
    return [r for r in load_incidents() if r.get("issue_type") == issue_type]
