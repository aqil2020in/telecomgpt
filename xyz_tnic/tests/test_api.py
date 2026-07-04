"""API integration tests."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient

from app.main import create_app


def test_health():
    client = TestClient(create_app())
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_rca_endpoint():
    client = TestClient(create_app())
    r = client.post("/api/v1/analyze/rca", json={
        "query": "Root cause low throughput",
        "issue_type": "throughput",
        "kpis": {"cqi": 7, "bler": 15, "throughput_mbps": 30},
        "include_rag": False,
        "generate_report": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["issue_type"] == "throughput"
    assert len(data["findings"]) >= 1


def test_health_score():
    client = TestClient(create_app())
    r = client.post("/api/v1/health-score/cell", json={
        "cell_id": "43211",
        "kpis": {"ss_sinr": 15, "ho_success_rate": 98, "call_drop_rate": 0.5},
    })
    assert r.status_code == 200
    assert r.json()["grade"] in ("A", "B", "C", "D")


if __name__ == "__main__":
    test_health()
    test_rca_endpoint()
    test_health_score()
    print("API tests passed.")
