"""Incident dataset tests."""

from __future__ import annotations

from tnic.services.incidents import get_incident, incidents_by_issue, load_incidents


def test_load_incidents():
    rows = load_incidents()
    assert len(rows) >= 10
    assert "incident_id" in rows[0]


def test_get_incident():
    row = get_incident("INC-2026-001")
    assert row["issue_type"] == "call_drop"


def test_incidents_by_issue():
    rows = incidents_by_issue("throughput")
    assert all(r["issue_type"] == "throughput" for r in rows)
    assert len(rows) >= 1
