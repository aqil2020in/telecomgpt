"""Tests for 5G Handover Failure Agent (ho_agent.py)."""

from __future__ import annotations

import os

import pandas as pd
import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from tnic.agents.ho_agent import (  # noqa: E402
    FAILURE_CODES,
    FAILURE_LABELS,
    HandoverFailureAgent,
    diagnose_handover,
)
from tnic.agents.specialists import HOAgent
from tnic.datasets.loaders import clear_loader_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_loader_cache()
    yield
    clear_loader_cache()


def _sample_events() -> pd.DataFrame:
    return pd.DataFrame([
        {"ue_id": "UE1", "cell_id": "XYZ401", "rsrp": -120, "rsrq": -14, "sinr": -2, "failure_type": "PREP_FAILURE"},
        {"ue_id": "UE2", "cell_id": "XYZ401", "rsrp": -118, "rsrq": -13, "sinr": 0, "failure_type": "PREP_FAILURE"},
        {"ue_id": "UE3", "cell_id": "XYZ401", "rsrp": -115, "rsrq": -12, "sinr": 2, "failure_type": "XN_FAILURE"},
        {"ue_id": "UE4", "cell_id": "XYZ401", "rsrp": -90, "rsrq": -8, "sinr": 18, "failure_type": "SUCCESS"},
    ])


def test_output_schema():
    agent = HandoverFailureAgent()
    result = agent.analyze(cell_id="XYZ401", events=_sample_events())
    payload = result.to_dict()
    assert set(payload.keys()) == {"failure_type", "root_cause", "confidence"}
    assert payload["failure_type"] == "Prep Failure"
    assert isinstance(payload["root_cause"], str) and len(payload["root_cause"]) > 20
    assert 0.0 < payload["confidence"] <= 0.95


def test_detect_all_failure_types():
    agent = HandoverFailureAgent()
    for code in FAILURE_CODES:
        df = pd.DataFrame([{
            "ue_id": "UE99",
            "cell_id": "XYZ402",
            "rsrp": -110,
            "rsrq": -12,
            "sinr": 5,
            "failure_type": code,
        }])
        result = agent.analyze(cell_id="XYZ402", events=df)
        assert result.failure_type == FAILURE_LABELS[code]
        assert result.root_cause
        assert result.confidence >= 0.35


@pytest.mark.parametrize("query,expected_label", [
    ("handover prep failure cell XYZ401", "Prep Failure"),
    ("Xn handover failure", "Xn Failure"),
    ("N2 NGAP handover timeout", "N2 Failure"),
    ("too late handover cell edge", "Too Late HO"),
    ("ping pong between neighbors", "Ping Pong"),
    ("wrong cell handover ranking", "Wrong Cell"),
])
def test_query_hints(query, expected_label):
    agent = HandoverFailureAgent()
    df = pd.DataFrame([
        {"ue_id": "UE1", "cell_id": "XYZ401", "rsrp": -110, "rsrq": -12, "sinr": 5, "failure_type": "XN_FAILURE"},
        {"ue_id": "UE2", "cell_id": "XYZ401", "rsrp": -112, "rsrq": -13, "sinr": 3, "failure_type": "PREP_FAILURE"},
    ])
    result = agent.analyze(cell_id="XYZ401", query=query, events=df)
    assert result.failure_type == expected_label


def test_loads_handover_events_csv():
    result = diagnose_handover(cell_id="XYZ401")
    assert result["failure_type"] in set(FAILURE_LABELS.values()) | {"No Failure", "No Data"}
    assert result["confidence"] > 0


def test_no_failures_returns_no_failure():
    df = pd.DataFrame([
        {"ue_id": "UE1", "cell_id": "XYZ410", "rsrp": -85, "rsrq": -8, "sinr": 20, "failure_type": "SUCCESS"},
    ])
    result = HandoverFailureAgent().analyze(cell_id="XYZ410", events=df)
    assert result.failure_type == "No Failure"


def test_ho_agent_specialist_integrates():
    from tnic.datasets.kpi_service import compute_cell_kpis

    kpis = compute_cell_kpis("XYZ401").kpis
    result = HOAgent().analyze(kpis, query="handover failure cell XYZ401")
    assert result.agent == "ho_agent"
    assert len(result.findings) >= 1
    assert result.findings[0].confidence > 0


def test_rf_context_in_root_cause():
    result = HandoverFailureAgent().analyze(cell_id="XYZ401", events=_sample_events())
    assert "RSRP" in result.root_cause
    assert "SINR" in result.root_cause
