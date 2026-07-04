"""Tests for 5G RACH Failure Agent (rach_agent.py)."""

from __future__ import annotations

import os

import pandas as pd
import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from tnic.agents.rach_agent import (  # noqa: E402
    MSG_LABELS,
    ROOT_CAUSE_LABELS,
    RACHFailureAgent,
    classify_root_cause,
    diagnose_rach,
)
from tnic.agents.specialists import RACHAgent as SpecialistRACHAgent
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
        {"ue_id": "UE1", "cell_id": "XYZ402", "msg_failure": "MSG3"},
        {"ue_id": "UE2", "cell_id": "XYZ402", "msg_failure": "MSG3"},
        {"ue_id": "UE3", "cell_id": "XYZ402", "msg_failure": "MSG1"},
    ])
    result = RACHFailureAgent().analyze(cell_id="XYZ402", events=df)
    payload = result.to_dict()
    assert set(payload.keys()) == {"failure_type", "root_cause", "confidence"}
    assert payload["failure_type"] == "MSG3 Failure"
    assert ROOT_CAUSE_LABELS["PRACH_MISCONFIG"] in payload["root_cause"]
    assert 0.0 < payload["confidence"] <= 0.95


@pytest.mark.parametrize("msg,expected", [
    ("MSG1", "MSG1 Failure"),
    ("MSG2", "MSG2 Failure"),
    ("MSG3", "MSG3 Failure"),
    ("MSG4", "MSG4 Failure"),
])
def test_detect_all_msg_failures(msg, expected):
    df = _events([{"ue_id": "UE1", "cell_id": "XYZ402", "msg_failure": msg}])
    result = RACHFailureAgent().analyze(cell_id="XYZ402", events=df)
    assert result.failure_type == expected


@pytest.mark.parametrize("msg,rsrp,sinr,expected_root", [
    ("MSG1", -118, 5, "Coverage"),
    ("MSG1", -100, -5, "Interference"),
    ("MSG1", -100, 10, "PRACH Misconfig"),
    ("MSG3", -115, 5, "Coverage"),
    ("MSG4", -90, 15, "Beam Issue"),
])
def test_classify_root_cause(msg, rsrp, sinr, expected_root):
    code = classify_root_cause(msg, rsrp, sinr)
    assert ROOT_CAUSE_LABELS[code] == expected_root


@pytest.mark.parametrize("query,expected_msg,expected_root", [
    ("RACH MSG3 failure cell", "MSG3 Failure", "PRACH Misconfig"),
    ("MSG1 preamble failure", "MSG1 Failure", "PRACH Misconfig"),
    ("RACH beam issue MSG4", "MSG4 Failure", "Beam Issue"),
    ("RACH coverage cell edge", "MSG1 Failure", "Coverage"),
])
def test_query_hints(query, expected_msg, expected_root):
    df = _events([
        {"ue_id": "UE1", "cell_id": "XYZ402", "msg_failure": "MSG1", "rsrp": -118, "sinr": 5},
        {"ue_id": "UE2", "cell_id": "XYZ402", "msg_failure": "MSG3"},
        {"ue_id": "UE3", "cell_id": "XYZ402", "msg_failure": "MSG4", "rsrp": -90, "sinr": 15},
    ])
    result = RACHFailureAgent().analyze(cell_id="XYZ402", query=query, events=df)
    assert result.failure_type == expected_msg
    assert expected_root in result.root_cause


def test_loads_rach_events_csv():
    result = diagnose_rach(cell_id="XYZ402")
    assert result["failure_type"] in set(MSG_LABELS.values()) | {"No Failure", "No Data"}
    assert result["confidence"] > 0


def test_no_failures():
    df = _events([{"ue_id": "UE1", "cell_id": "XYZ410", "msg_failure": "SUCCESS"}])
    result = RACHFailureAgent().analyze(cell_id="XYZ410", events=df)
    assert result.failure_type == "No Failure"


def test_specialist_integrates():
    from tnic.datasets.kpi_service import compute_cell_kpis

    kpis = compute_cell_kpis("XYZ402").kpis
    result = SpecialistRACHAgent().analyze(kpis, query="RACH MSG3 cell XYZ402")
    assert result.agent == "rach_agent"
    assert len(result.findings) >= 1


def test_xyz402_rach_demo_cell():
    """XYZ402 is the bad-RACH profile cell in demo datasets."""
    result = RACHFailureAgent().analyze(cell_id="XYZ402")
    assert result.failure_type in MSG_LABELS.values()
    assert result.evidence is not None
    assert result.evidence["total_failures"] >= 10
