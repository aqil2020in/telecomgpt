"""Tests for RCA assistant. Run: python backend/test_rca_assistant.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics.rca_assistant import (
    apply_rules,
    explain_rca_assistant,
    load_rca_workflows,
    looks_like_rca_query,
    match_workflows,
    parse_inline_kpis,
    run_rca_assistant,
)


def test_load_workflows():
    data = load_rca_workflows()
    assert data.get("workflows")
    ids = {w["id"] for w in data["workflows"]}
    assert "call_drop" in ids
    assert "low_throughput" in ids
    assert "rach_failure" in ids
    assert "handover_failure" in ids
    assert "high_latency" in ids


def test_looks_like_rca():
    assert looks_like_rca_query("Root cause analysis call drop")
    assert looks_like_rca_query("RCA low throughput CQI=7 BLER=15%")
    assert looks_like_rca_query("troubleshoot handover failure")
    assert looks_like_rca_query("RACH failure root cause")
    assert not looks_like_rca_query("What is band n78?")
    assert not looks_like_rca_query("Explain SINR vs RSRQ link budget")
    assert not looks_like_rca_query("Fault analysis RRC fail HARQ K1")


def test_match_workflows():
    hits = match_workflows("root cause low throughput high BLER")
    assert hits and hits[0]["id"] == "low_throughput"
    assert match_workflows("handover failure missing neighbor")[0]["id"] == "handover_failure"


def test_parse_inline_kpis():
    kpis = parse_inline_kpis("CQI=7.3 DL BLER 15% SINR=-2 RSRP=-95")
    assert kpis["cqi"] == 7.3
    assert kpis["bler"] == 15.0
    assert kpis["ss_sinr"] == -2.0
    assert kpis["ss_rsrp"] == -95.0


def test_apply_rules():
    wf = next(w for w in load_rca_workflows()["workflows"] if w["id"] == "low_throughput")
    hits = apply_rules(wf, {"cqi": 7.0, "bler": 12.0})
    assert hits
    assert hits[0]["probable_cause"]
    assert hits[0]["confidence"] >= 0.65


def test_run_rca_with_kpis():
    result = run_rca_assistant("RCA low throughput CQI=7 BLER=15% stuck rank-1")
    assert result["ok"]
    assert result["issue_id"] == "low_throughput"
    assert result["probable_causes"]
    assert result["recommended_actions"]
    assert result["validation_checklist"]
    assert "cqi" in result["related_kpis"]


def test_explain_markdown():
    md = explain_rca_assistant("root cause call drop")
    assert "RCA Assistant" in md
    assert "Probable root causes" in md
    assert "Validation checklist" in md


def test_core_instant_path():
    from telecom_ai.core import TelecomAI

    db = Path(__file__).resolve().parent / "data" / "telecom_master_db.json"
    ai = TelecomAI(str(db))
    out = ai._instant_answer("Root cause analysis RACH failure")
    assert out and "RCA Assistant" in out


if __name__ == "__main__":
    test_load_workflows()
    test_looks_like_rca()
    test_match_workflows()
    test_parse_inline_kpis()
    test_apply_rules()
    test_run_rca_with_kpis()
    test_explain_markdown()
    test_core_instant_path()
    print("All RCA assistant tests passed.")
