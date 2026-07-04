"""Tests for telecom dataset loaders, validation, and KPI service."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")


def test_load_all_dataframes():
    from tnic.datasets.loaders import load_all_dataframes

    frames = load_all_dataframes()
    assert len(frames) == 6
    assert len(frames["pm_counters"]) >= 1000
    assert "cell_id" in frames["handover_events"].columns


def test_validate_all_datasets():
    from tnic.datasets.validation import validate_all

    results = validate_all()
    assert len(results) == 6
    assert all(r.ok for r in results)


@pytest.mark.parametrize("name", [
    "pm_counters", "handover_events", "rlf_events",
    "rach_events", "call_drop_events", "throughput_metrics",
])
def test_summarize_dataset(name):
    from tnic.datasets.summary import summarize_dataset

    s = summarize_dataset(name)
    assert s.row_count >= 1000
    assert s.cell_count >= 5


def test_compute_cell_kpis_xyz401():
    from tnic.datasets.kpi_service import compute_cell_kpis

    bundle = compute_cell_kpis("XYZ401")
    assert bundle.cell_id == "XYZ401"
    assert "ho_success_rate" in bundle.kpis or "call_drop_rate" in bundle.kpis
    assert len(bundle.sources) >= 3
    assert bundle.health_score is not None


def test_build_kpi_input_from_query():
    from tnic.datasets.kpi_service import build_kpi_input

    kpi = build_kpi_input(query="Root cause call drop on cell XYZ405")
    assert kpi.cell_id == "XYZ405"
    assert kpi.ho_success_rate is not None or kpi.call_drop_rate is not None


def test_orchestrator_uses_dataset_kpis():
    from tnic.models.schemas import AnalyzeRequest
    from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator

    orch = MasterRCAOrchestrator()
    result = orch.run(AnalyzeRequest(query="Root cause analysis call drop cell XYZ401"))
    assert result.issue_type == "call_drop"
    assert len(result.agents_run) >= 3
    assert result.health_score is not None


def test_datasets_api_summary():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.get("/api/v1/datasets/summary")
    assert r.status_code == 200
    assert r.json()["dataset_count"] == 6
