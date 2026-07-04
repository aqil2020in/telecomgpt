"""Tests for the 5G Beamforming Agent."""

from __future__ import annotations

import os

import pandas as pd
import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")


@pytest.fixture(autouse=True)
def _clear_loader_cache():
    from tnic.datasets.loaders import clear_loader_cache

    clear_loader_cache()
    yield
    clear_loader_cache()


@pytest.fixture
def agent():
    from tnic.agents.beam_agent import BeamformingAgent

    return BeamformingAgent()


def test_diagnose_schema(agent):
    from tnic.agents.beam_agent import diagnose_beamforming

    result = diagnose_beamforming(cell_id="XYZ401")
    assert set(result.keys()) >= {"issue_class", "root_cause", "confidence", "metrics"}
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.parametrize(
    "util,switches,rsrp,sinr,ratio,expected",
    [
        (90.0, 5, -95.0, 12.0, 1.2, "BEAM_CONGESTION"),
        (50.0, 16, -95.0, 6.0, 1.2, "BEAM_INSTABILITY"),
        (50.0, 5, -112.0, 8.0, 1.2, "BEAM_COVERAGE_HOLE"),
        (50.0, 5, -95.0, 12.0, 3.0, "BEAM_IMBALANCE"),
    ],
)
def test_classify_beam_issue(util, switches, rsrp, sinr, ratio, expected):
    from tnic.agents.beam_agent import classify_beam_issue

    assert classify_beam_issue(util, switches, rsrp, sinr, ratio) == expected


def test_synthesize_beam_metrics_shape(agent):
    from tnic.agents.beam_agent import synthesize_beam_metrics

    df = synthesize_beam_metrics("XYZ401")
    assert len(df) == 8
    assert set(df.columns) >= {
        "cell_id",
        "beam_index",
        "beam_utilization",
        "beam_switches",
        "rsrp",
        "sinr",
    }
    assert (df["cell_id"] == "XYZ401").all()


def test_analyze_xyz401_detects_beam_issues(agent):
    result = agent.analyze(cell_id="XYZ401")
    assert result.issue_class in {
        "Beam Congestion",
        "Beam Instability",
        "Beam Coverage Hole",
        "Beam Imbalance",
    }
    assert result.confidence >= 0.5
    metrics = result.metrics or {}
    assert metrics.get("beam_utilization") is not None
    assert metrics.get("beam_switches") is not None
    assert metrics.get("rsrp") is not None
    assert metrics.get("sinr") is not None


@pytest.mark.parametrize(
    "query,expected_label",
    [
        ("beam congestion on XYZ401", "Beam Congestion"),
        ("beam coverage hole XYZ401", "Beam Coverage Hole"),
        ("beam instability switches", "Beam Instability"),
        ("beam imbalance load", "Beam Imbalance"),
    ],
)
def test_query_hints(agent, query, expected_label):
    result = agent.analyze(cell_id="XYZ401", query=query)
    assert result.issue_class == expected_label


def test_explicit_dataframe_congestion(agent):
    beams = pd.DataFrame([
        {"cell_id": "T1", "beam_index": 0, "beam_utilization": 92, "beam_switches": 4, "rsrp": -95, "sinr": 14},
        {"cell_id": "T1", "beam_index": 1, "beam_utilization": 88, "beam_switches": 3, "rsrp": -94, "sinr": 13},
    ])
    result = agent.analyze(cell_id="T1", beams=beams)
    assert result.issue_class == "Beam Congestion"


def test_explicit_dataframe_coverage_hole(agent):
    beams = pd.DataFrame([
        {"cell_id": "T2", "beam_index": 0, "beam_utilization": 40, "beam_switches": 3, "rsrp": -115, "sinr": 5},
    ])
    result = agent.analyze(cell_id="T2", beams=beams)
    assert result.issue_class == "Beam Coverage Hole"


def test_explicit_dataframe_imbalance(agent):
    beams = pd.DataFrame([
        {"cell_id": "T3", "beam_index": 0, "beam_utilization": 90, "beam_switches": 4, "rsrp": -95, "sinr": 12},
        {"cell_id": "T3", "beam_index": 1, "beam_utilization": 30, "beam_switches": 3, "rsrp": -94, "sinr": 11},
    ])
    result = agent.analyze(cell_id="T3", beams=beams)
    assert result.issue_class == "Beam Imbalance"


def test_specialist_wrapper_with_cell_id():
    from tnic.agents.specialists import BeamformingAgent

    result = BeamformingAgent().analyze({"cell_id": "XYZ401"}, query="beam issue")
    assert result.agent == "beamforming_agent"
    assert len(result.findings) == 1
    assert result.findings[0].category == "beamforming"
    assert result.findings[0].confidence >= 0.5


def test_specialist_wrapper_falls_back_to_rules(degraded_kpis):
    from tnic.agents.specialists import BeamformingAgent

    kpis = {**degraded_kpis, "beam_switch_rate": 15, "beam_failure_ratio": 32}
    result = BeamformingAgent().analyze(kpis, query="beam failure")
    assert result.agent == "beamforming_agent"
    assert len(result.findings) >= 1


def test_no_data_when_empty_scope(agent):
    result = agent.analyze()
    assert result.issue_class == "No Data"
    assert result.confidence == 0.0
