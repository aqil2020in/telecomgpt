"""Tests for 5G Radio Link Failure Agent (rlf_agent.py)."""

from __future__ import annotations

import os

import pandas as pd
import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from tnic.agents.rlf_agent import (  # noqa: E402
    N310_RL_FAILURE_THRESHOLD,
    RLFAgent,
    RLF_LABELS,
    classify_rlf_event,
    derive_n310,
    derive_t310_expired,
    diagnose_rlf,
)
from tnic.agents.specialists import RLFAgent as SpecialistRLFAgent
from tnic.datasets.loaders import clear_loader_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_loader_cache()
    yield
    clear_loader_cache()


def _events(**overrides) -> pd.DataFrame:
    base = {
        "ue_id": "UE1",
        "cell_id": "XYZ401",
        "rsrp": -115.0,
        "sinr": -5.0,
        "cause": "Coverage",
    }
    base.update(overrides)
    return pd.DataFrame([base])


def test_output_schema():
    agent = RLFAgent()
    result = agent.analyze(cell_id="XYZ401", events=_events())
    payload = result.to_dict()
    assert set(payload.keys()) == {"rlf_type", "root_cause", "confidence"}
    assert payload["rlf_type"] == "Coverage Hole"
    assert "RSRP" in payload["root_cause"]
    assert "N310" in payload["root_cause"]
    assert 0.0 < payload["confidence"] <= 0.95


@pytest.mark.parametrize("rsrp,sinr,cause,expected", [
    (-118, -12, "Coverage", "Coverage Hole"),
    (-102, -8, "Interference", "Interference"),
    (-96, 2, "Post_HO", "Post-HO RLF"),
    (-108, -15, None, "Radio Failure"),
])
def test_classify_rlf_event(rsrp, sinr, cause, expected):
    code = classify_rlf_event(rsrp, sinr, cause)
    assert RLF_LABELS[code] == expected


def test_n310_t310_derivation():
    assert derive_n310(-115, -12) >= N310_RL_FAILURE_THRESHOLD
    assert derive_t310_expired(-115, -12, 5) is True
    assert derive_n310(-90, 15) == 0
    assert derive_t310_expired(-90, 15, 0) is False


def test_detect_all_rlf_types():
    agent = RLFAgent()
    samples = [
        {"rsrp": -118, "sinr": -10, "cause": "Coverage"},
        {"rsrp": -102, "sinr": -6, "cause": "Interference"},
        {"rsrp": -95, "sinr": 3, "cause": "Post_HO"},
        {"rsrp": -105, "sinr": -12, "cause": "None", "n310": 5, "t310": 1},
    ]
    for i, row in enumerate(samples):
        df = pd.DataFrame([{"ue_id": f"UE{i}", "cell_id": "XYZ403", **row}])
        result = agent.analyze(cell_id="XYZ403", events=df)
        assert result.rlf_type in set(RLF_LABELS.values())
        assert result.confidence >= 0.35


@pytest.mark.parametrize("query,expected", [
    ("RLF coverage hole cell edge", "Coverage Hole"),
    ("interference induced RLF", "Interference"),
    ("RLF after handover", "Post-HO RLF"),
    ("N310 T310 sync failure RLF", "Radio Failure"),
])
def test_query_hints(query, expected):
    df = pd.DataFrame([
        {"ue_id": "UE1", "cell_id": "XYZ401", "rsrp": -102, "sinr": -6, "cause": "Interference"},
        {"ue_id": "UE2", "cell_id": "XYZ401", "rsrp": -118, "sinr": -8, "cause": "Coverage"},
    ])
    result = RLFAgent().analyze(cell_id="XYZ401", query=query, events=df)
    assert result.rlf_type == expected


def test_loads_rlf_events_csv():
    result = diagnose_rlf(cell_id="XYZ401")
    assert result["rlf_type"] in set(RLF_LABELS.values()) | {"No RLF", "No Data"}
    assert result["confidence"] > 0


def test_specialist_integrates():
    from tnic.datasets.kpi_service import compute_cell_kpis

    kpis = compute_cell_kpis("XYZ401").kpis
    result = SpecialistRLFAgent().analyze(kpis, query="RLF radio link failure cell XYZ401")
    assert result.agent == "rlf_agent"
    assert len(result.findings) >= 1


def test_explicit_n310_t310_columns():
    df = pd.DataFrame([{
        "ue_id": "UE99",
        "cell_id": "XYZ402",
        "rsrp": -100,
        "sinr": 2,
        "cause": "None",
        "n310": 6,
        "t310": 1,
    }])
    result = RLFAgent().analyze(cell_id="XYZ402", events=df)
    assert result.rlf_type == "Radio Failure"
    assert result.evidence is not None
    assert result.evidence.get("mean_n310", 0) >= N310_RL_FAILURE_THRESHOLD
