"""Tests for dynamic upload and ingestion framework."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os_env = __import__("os")
os_env.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from tnic.services.dynamic_rca import ingest_and_run_rca, run_dynamic_rca
from tnic.services.event_repository import load_events, list_uploads
from tnic.services.file_classifier import classify_file
from tnic.services.ingest_pipeline import ingest_uploaded_bytes
from tnic.services.normalization_engine import normalize_uploaded_file, summarize_events
from tnic.services.events_kpi_bridge import kpis_from_events


UE_CSV = b"""timestamp,ue_id,cell_id,layer,procedure,message,result,cause
2026-07-01 10:05:04,UE10002,XYZ401,RACH,ACCESS,RACH_FAILURE,FAIL,NO_RAR_RESPONSE
2026-07-01 10:10:03,UE10003,XYZ401,NAS,REGISTRATION,REGISTRATION_REJECT,FAIL,TA_NOT_ALLOWED
"""

SYSLOG_TXT = b"""2026-07-01 10:00:00 DU HO_PREP_FAIL cell XYZ401 NGAP HandoverPreparationFailure
2026-07-01 10:01:00 CU T310_EXPIRED RLF out-of-sync cell XYZ401
"""

RF_CSV = b"""timestamp,cell_id,ue_id,rsrp,sinr,cqi
2026-07-01 10:00:00,XYZ401,UE10001,-110,5,8
2026-07-01 10:01:00,XYZ401,UE10002,-110,5,8
"""


def test_classify_ue_trace_columns():
    clf = classify_file("ue_protocol_trace.csv", columns=["ue_id", "layer", "procedure", "message", "result"])
    assert clf.file_type == "UE_PROTOCOL_TRACE"
    assert clf.confidence >= 0.5


def test_classify_gnb_syslog_patterns():
    clf = classify_file("gnb.log", text_sample=SYSLOG_TXT.decode())
    assert clf.file_type == "GNB_SYSLOG"
    assert clf.confidence >= 0.25


def test_classify_rf_columns():
    clf = classify_file("drive_test.csv", columns=["rsrp", "sinr", "cqi", "cell_id"])
    assert clf.file_type == "RF_MEASUREMENT"


def test_ingest_ue_csv():
    result = ingest_uploaded_bytes("ue_upload.csv", UE_CSV)
    assert result.ok
    assert result.classification.file_type == "UE_PROTOCOL_TRACE"
    assert result.event_count >= 2
    assert result.failure_count >= 2
    assert "XYZ401" in result.cell_ids
    assert "UE10002" in result.ue_ids


def test_ingest_syslog_txt():
    result = ingest_uploaded_bytes("gnb_syslog.log", SYSLOG_TXT)
    assert result.ok
    assert result.classification.file_type == "GNB_SYSLOG"
    assert result.event_count >= 1


def test_normalized_event_model():
    result = ingest_uploaded_bytes("rf.csv", RF_CSV)
    events = load_events(result.upload_id)
    assert events
    summary = summarize_events(events)
    assert summary["event_count"] == len(events)


def test_kpis_from_events():
    result = ingest_uploaded_bytes("ue_kpi.csv", UE_CSV)
    events = load_events(result.upload_id)
    kpis = kpis_from_events(events, "XYZ401")
    assert kpis["normalized_event_count"] >= 2
    assert kpis.get("ue_trace_failure_count", 0) >= 2


def test_dynamic_rca_from_upload():
    ingest = ingest_uploaded_bytes("ue_rca.csv", UE_CSV)
    rca = run_dynamic_rca(ingest.upload_id, cell_id="XYZ401", query="UE RACH failure XYZ401")
    assert rca.events_used >= 2
    assert rca.rca.get("issue_type")
    assert len(rca.rca.get("findings", [])) >= 1


def test_ingest_and_run_rca_one_shot():
    out = ingest_and_run_rca("ue_one_shot.csv", UE_CSV, cell_id="XYZ401")
    assert out.ingest is not None
    assert out.ingest.ok
    assert out.rca.get("agents_run")


def test_upload_api_endpoint():
    from fastapi.testclient import TestClient
    from tnic.main import create_app

    client = TestClient(create_app())
    r = client.post(
        "/api/v1/upload",
        files={"file": ("test_ue.csv", BytesIO(UE_CSV), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["classification"]["file_type"] == "UE_PROTOCOL_TRACE"


def test_list_uploads_after_ingest():
    ingest_uploaded_bytes("list_test.csv", UE_CSV)
    uploads = list_uploads(limit=5)
    assert len(uploads) >= 1
