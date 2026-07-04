"""Demo readiness — API aliases, cell profile, domain ranking."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")


def test_analyze_ho_alias():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.post(
        "/api/v1/analyze-ho",
        json={"query": "handover failure cell XYZ401"},
    )
    assert r.status_code == 200
    assert r.json()["issue_type"] == "handover"
    assert len(r.json()["findings"]) >= 1


def test_analyze_rach_hyphen_alias():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.post(
        "/api/v1/analyze-rach",
        json={"query": "RACH MSG3 cell XYZ401"},
    )
    assert r.status_code == 200
    assert r.json()["issue_type"] == "rach"


def test_generate_rca_endpoint():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.post(
        "/api/v1/generate-rca",
        json={"query": "call drop cell XYZ401", "cell_id": "XYZ401", "generate_report": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["issue_type"] == "call_drop"
    assert body["probable_root_causes"][0]["category"] == "call_drop"


def test_analyze_cell_endpoint():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.post(
        "/api/v1/analyze-cell",
        json={"cell_id": "XYZ401", "issue_type": "call_drop"},
    )
    assert r.status_code == 200
    assert r.json()["issue_type"] == "call_drop"


def test_analyze_cell_unknown_returns_404():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.post("/api/v1/analyze-cell", json={"cell_id": "UNKNOWN999"})
    assert r.status_code == 404


def test_get_cell_profile():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.get("/api/v1/cell/XYZ401")
    assert r.status_code == 200
    body = r.json()
    assert body["cell_id"] == "XYZ401"
    assert "health_score" in body
    assert "kpis" in body
    assert body["incident_count"] >= 0


def test_get_cell_unknown_returns_404():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.get("/api/v1/cell/UNKNOWN999")
    assert r.status_code == 404


def test_rlf_query_ranks_rlf_finding_first():
    from tnic.models.schemas import AnalyzeRequest
    from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator

    result = MasterRCAOrchestrator().run(
        AnalyzeRequest(query="RLF radio link failure cell XYZ401")
    )
    assert result.issue_type == "rlf"
    assert result.findings
    assert result.findings[0].category == "rlf"


@pytest.mark.parametrize(
    "issue,query",
    [
        ("call_drop", "Root cause call drop cell XYZ401"),
        ("handover", "handover failure cell XYZ401"),
        ("rach", "RACH MSG3 cell XYZ401"),
    ],
)
def test_demo_queries_primary_category_first(issue, query):
    from tnic.models.schemas import AnalyzeRequest
    from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator

    result = MasterRCAOrchestrator().run(AnalyzeRequest(query=query))
    assert result.issue_type == issue
    top = result.probable_root_causes[0]
    assert top["category"] == issue
