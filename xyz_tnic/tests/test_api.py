"""FastAPI integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tnic.main import create_app


def test_health_endpoint():
    client = TestClient(create_app())
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "chroma" in body


def test_rca_endpoint(degraded_kpis):
    client = TestClient(create_app())
    r = client.post(
        "/api/v1/analyze/rca",
        json={
            "query": "Root cause call drop",
            "kpis": degraded_kpis,
            "include_rag": True,
            "generate_report": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["issue_type"] == "call_drop"
    assert len(body["agents_run"]) >= 3


def test_incidents_list():
    client = TestClient(create_app())
    r = client.get("/api/v1/incidents")
    assert r.status_code == 200
    assert r.json()["count"] >= 10


def test_cell_health_endpoint():
    client = TestClient(create_app())
    r = client.post(
        "/api/v1/health-score/cell",
        json={"cell_id": "43211", "kpis": {"ho_success_rate": 91.0, "call_drop_rate": 3.2}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cell_id"] == "43211"
    assert "overall_score" in body
