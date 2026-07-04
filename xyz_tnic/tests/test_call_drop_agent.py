"""Tests for 5G Call Drop Agent (call_drop_agent.py)."""

from __future__ import annotations

import os

import pandas as pd
import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from tnic.agents.call_drop_agent import (  # noqa: E402
    DROP_LABELS,
    CallDropAgent,
    diagnose_call_drop,
)
from tnic.agents.specialists import CallDropAgent as SpecialistCallDropAgent
from tnic.datasets.loaders import clear_loader_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_loader_cache()
    yield
    clear_loader_cache()


def _events(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_output_schema():
    df = _events([
        {"ue_id": "UE1", "cell_id": "XYZ401", "drop_type": "Mobility"},
        {"ue_id": "UE2", "cell_id": "XYZ401", "drop_type": "Mobility"},
        {"ue_id": "UE3", "cell_id": "XYZ401", "drop_type": "Radio"},
    ])
    result = CallDropAgent().analyze(cell_id="XYZ401", events=df)
    payload = result.to_dict()
    assert set(payload.keys()) == {"root_cause", "confidence"}
    assert "Mobility Drop" in payload["root_cause"]
    assert 0.0 < payload["confidence"] <= 0.95


@pytest.mark.parametrize("drop_type,expected_label", [
    ("Radio", "Radio Drop"),
    ("Mobility", "Mobility Drop"),
    ("IMS", "IMS Drop"),
    ("Core", "Core Drop"),
    ("Transport", "Transport Drop"),
])
def test_classify_all_drop_types(drop_type, expected_label):
    df = _events([{"ue_id": "UE1", "cell_id": "XYZ402", "drop_type": drop_type}])
    result = CallDropAgent().analyze(cell_id="XYZ402", events=df)
    assert result.drop_class == expected_label
    assert expected_label in result.root_cause


@pytest.mark.parametrize("query,expected", [
    ("call drop mobility handover", "Mobility Drop"),
    ("radio layer RLF drop", "Radio Drop"),
    ("IMS VoNR drop", "IMS Drop"),
    ("AMF core release drop", "Core Drop"),
    ("transport backhaul N3 drop", "Transport Drop"),
])
def test_query_hints(query, expected):
    df = _events([
        {"ue_id": "UE1", "cell_id": "XYZ401", "drop_type": "Radio"},
        {"ue_id": "UE2", "cell_id": "XYZ401", "drop_type": "Core"},
    ])
    result = CallDropAgent().analyze(cell_id="XYZ401", query=query, events=df)
    assert result.drop_class == expected


def test_dominant_drop_type_wins_without_hint():
    df = _events([
        {"ue_id": f"UE{i}", "cell_id": "XYZ401", "drop_type": "IMS"}
        for i in range(5)
    ] + [
        {"ue_id": f"UE{i+10}", "cell_id": "XYZ401", "drop_type": "Radio"}
        for i in range(2)
    ])
    result = CallDropAgent().analyze(cell_id="XYZ401", events=df)
    assert result.drop_class == "IMS Drop"


def test_loads_call_drop_events_csv():
    result = diagnose_call_drop(cell_id="XYZ401")
    assert "root_cause" in result
    assert result["confidence"] > 0


def test_no_data():
    result = CallDropAgent().analyze(cell_id="UNKNOWN999", events=_events([]))
    assert result.confidence == 0.0
    assert "No call drop events" in result.root_cause


def test_specialist_integrates():
    from tnic.datasets.kpi_service import compute_cell_kpis

    kpis = compute_cell_kpis("XYZ401").kpis
    result = SpecialistCallDropAgent().analyze(kpis, query="root cause call drop cell XYZ401")
    assert result.agent == "call_drop_agent"
    assert len(result.findings) >= 1
    assert result.findings[0].confidence > 0


def test_xyz401_drop_distribution():
    """XYZ401 is a bad call-drop demo cell — should classify a primary drop type."""
    result = CallDropAgent().analyze(cell_id="XYZ401")
    assert result.drop_class in set(DROP_LABELS.values())
    assert result.evidence is not None
    assert result.evidence["total_drops"] >= 10
