"""Tests for Throughput Analysis Agent (throughput_agent.py)."""

from __future__ import annotations

import os

import pandas as pd
import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from tnic.agents.specialists import ThroughputAgent as SpecialistThroughputAgent
from tnic.agents.throughput_agent import (  # noqa: E402
    ISSUE_LABELS,
    ThroughputAnalysisAgent,
    classify_throughput_issue,
    derive_bler,
    derive_mcs,
    diagnose_throughput,
)
from tnic.datasets.loaders import clear_loader_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_loader_cache()
    yield
    clear_loader_cache()


def _row(**kwargs) -> pd.DataFrame:
    base = {"cell_id": "XYZ404", "cqi": 8.0, "prb_util": 55.0, "dl_tp": 400.0, "issue": "None"}
    base.update(kwargs)
    return pd.DataFrame([base])


def test_output_schema():
    result = ThroughputAnalysisAgent().analyze(cell_id="XYZ404", metrics=_row(cqi=5, issue="RF"))
    payload = result.to_dict()
    assert "issue_class" in payload
    assert "root_cause" in payload
    assert "confidence" in payload
    assert "metrics" in payload
    for key in ("cqi", "mcs", "prb_utilization", "bler", "dl_throughput_mbps"):
        assert key in payload["metrics"]
    assert 0.0 < payload["confidence"] <= 0.95


@pytest.mark.parametrize("cqi,prb,bler,issue,expected", [
    (5, 30, 15, "RF", "RF Issue"),
    (12, 90, 3, "Congestion", "Congestion"),
    (11, 65, 4, "Scheduler", "Scheduler Issue"),
    (13, 25, 2, "Backhaul", "Backhaul Issue"),
])
def test_classify_issue_types(cqi, prb, bler, issue, expected):
    mcs = derive_mcs(cqi)
    code = classify_throughput_issue(cqi, mcs, prb, bler, dl_tp=100.0, labeled_issue=issue)
    assert ISSUE_LABELS[code] == expected


def test_derive_mcs_bler():
    assert derive_mcs(15) >= derive_mcs(5)
    assert derive_bler(4, 40) > derive_bler(12, 40)


@pytest.mark.parametrize("query,expected", [
    ("low throughput RF issue CQI", "RF Issue"),
    ("PRB congestion high utilization", "Congestion"),
    ("scheduler issue PRB allocation", "Scheduler Issue"),
    ("backhaul N3 bottleneck", "Backhaul Issue"),
])
def test_query_hints(query, expected):
    df = pd.DataFrame([
        {"cell_id": "XYZ404", "cqi": 12, "prb_util": 40, "dl_tp": 500, "issue": "Backhaul"},
        {"cell_id": "XYZ404", "cqi": 5, "prb_util": 30, "dl_tp": 120, "issue": "RF"},
    ])
    result = ThroughputAnalysisAgent().analyze(cell_id="XYZ404", query=query, metrics=df)
    assert result.issue_class == expected


def test_loads_throughput_csv():
    result = diagnose_throughput(cell_id="XYZ404")
    assert result["issue_class"] in set(ISSUE_LABELS.values()) | {"No Issue", "No Data"}
    assert result["metrics"]["dl_throughput_mbps"] is not None


def test_ul_throughput_from_pm_counters():
    result = ThroughputAnalysisAgent().analyze(cell_id="XYZ404")
    assert result.metrics is not None
    assert result.metrics.get("ul_throughput_mbps") is not None


def test_specialist_integrates():
    from tnic.datasets.kpi_service import compute_cell_kpis

    kpis = compute_cell_kpis("XYZ404").kpis
    result = SpecialistThroughputAgent().analyze(kpis, query="low throughput cell XYZ404")
    assert result.agent == "throughput_agent"
    assert len(result.findings) >= 1


def test_dominant_issue_without_hint():
    df = pd.DataFrame([
        {"cell_id": "XYZ403", "cqi": 4, "prb_util": 25, "dl_tp": 150, "issue": "RF"},
        {"cell_id": "XYZ403", "cqi": 5, "prb_util": 28, "dl_tp": 180, "issue": "RF"},
        {"cell_id": "XYZ403", "cqi": 11, "prb_util": 88, "dl_tp": 300, "issue": "Congestion"},
    ])
    result = ThroughputAnalysisAgent().analyze(cell_id="XYZ403", metrics=df)
    assert result.issue_class == "RF Issue"
