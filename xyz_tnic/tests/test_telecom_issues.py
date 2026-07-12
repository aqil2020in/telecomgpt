"""Tests for unified telecom_issues dataset and upload RCA."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from tnic.datasets.loaders import load_telecom_issues
from tnic.datasets.telecom_issues import (
    aggregate_kpis_from_issues_df,
    detect_key_issues,
    events_to_issues_dataframe,
)
from tnic.services.dynamic_rca import ingest_and_run_rca
from tnic.services.file_classifier import classify_file
from tnic.services.ingest_pipeline import ingest_uploaded_bytes
from tnic.services.events_kpi_bridge import kpis_from_events
from tnic.services.event_repository import load_events


def test_telecom_issues_csv_exists():
    df = load_telecom_issues()
    assert len(df) > 1000
    assert "issue_domain" in df.columns
    assert "event_type" in df.columns
    domains = set(df["issue_domain"].unique())
    assert "handover" in domains
    assert "rlf" in domains
    assert "vonr" in domains


def test_classify_telecom_issues_columns():
    clf = classify_file(
        "telecom_issues.csv",
        columns=["timestamp", "cell_id", "issue_domain", "event_type", "result"],
    )
    assert clf.file_type == "TELECOM_ISSUES"
    assert clf.confidence >= 0.5


def test_aggregate_kpis_xyz401():
    df = load_telecom_issues()
    kpis = aggregate_kpis_from_issues_df(df, "XYZ401")
    assert kpis["cell_id"] == "XYZ401"
    assert kpis.get("ho_success_rate") is not None
    assert kpis.get("telecom_issues_event_count", 0) > 0
    issues = detect_key_issues(kpis)
    assert isinstance(issues, list)


def test_ingest_telecom_issues_subset():
    csv = b"""timestamp,cell_id,ue_id,issue_domain,event_type,result,cause,rsrp,sinr
2026-07-01T10:00:00,XYZ401,UE1,handover,PREP_FAILURE,FAIL,,-110,5
2026-07-01T10:01:00,XYZ401,UE2,handover,SUCCESS,SUCCESS,,-95,12
2026-07-01T10:02:00,XYZ401,UE3,rlf,RLF,FAIL,Post_HO,-100,1
2026-07-01T10:03:00,XYZ401,UE4,rach,MSG2,FAIL,,,
2026-07-01T10:04:00,XYZ401,UE5,call_drop,Mobility,FAIL,Mobility,,
2026-07-01T10:05:00,XYZ401,UE6,vonr,SIP_BYE,DROP,IMS_TIMEOUT,,
"""
    result = ingest_uploaded_bytes("telecom_issues.csv", csv)
    assert result.ok
    assert result.classification.file_type == "TELECOM_ISSUES"
    assert result.event_count == 6
    assert result.failure_count >= 4
    assert "XYZ401" in result.cell_ids

    events = load_events(result.upload_id)
    kpis = kpis_from_events(events, "XYZ401")
    assert kpis.get("ho_prep_fail_rate") is not None
    assert kpis.get("rlf_event_count", 0) >= 1
    assert kpis.get("key_issues")


def test_upload_rca_telecom_issues():
    path = Path("/workspace/datasets/telecom_issues.csv")
    if not path.exists():
        pytest.skip("telecom_issues.csv not generated")
    content = path.read_bytes()
    # Use subset via small inline file for speed
    csv = b"""timestamp,cell_id,ue_id,issue_domain,event_type,result,cause,rsrp,sinr
2026-07-01T10:00:00,XYZ401,UE1,handover,PREP_FAILURE,FAIL,,-110,5
2026-07-01T10:01:00,XYZ401,UE2,handover,XN_FAILURE,FAIL,,-108,4
2026-07-01T10:02:00,XYZ401,UE3,rlf,RLF,FAIL,Post_HO,-100,1
2026-07-01T10:03:00,XYZ401,UE4,rach,MSG3,FAIL,,,
2026-07-01T10:05:00,XYZ401,UE6,vonr,SIP_BYE,DROP,IMS_TIMEOUT,,
"""
    out = ingest_and_run_rca("telecom_issues_demo.csv", csv, cell_id="XYZ401")
    assert out.ingest is not None
    assert out.ingest.ok
    assert out.rca.get("issue_type")
    assert len(out.rca.get("findings", [])) >= 1


def test_events_to_issues_dataframe_roundtrip():
    csv = b"""timestamp,cell_id,issue_domain,event_type,result
2026-07-01T10:00:00,XYZ402,throughput,RF,FAIL
"""
    ingest = ingest_uploaded_bytes("ti.csv", csv)
    events = load_events(ingest.upload_id)
    df = events_to_issues_dataframe(events)
    assert len(df) == 1
    assert df.iloc[0]["issue_domain"] == "throughput"
