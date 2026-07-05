"""Tests for UE Protocol Correlation Agent."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tnic.agents.ue_agent import UEProtocolAgent
from tnic.datasets.validation import validate_dataset
from tnic.orchestrator.master_rca import enrich_master_rca
from tnic.parsers.ue_trace_parser import UETraceParser
from tnic.rules.ue_rca_rules import build_ue_rca_from_event
from tnic.services.ue_correlation_service import compute_ue_confidence, correlate_cell_ue_failures


def test_ue_protocol_trace_validates():
    result = validate_dataset("ue_protocol_trace")
    assert result.row_count > 0
    assert result.ok, result.issues


def test_parser_failures_for_cell():
    parser = UETraceParser()
    fails = parser.failures_for_cell("XYZ401")
    assert len(fails) >= 10
    summary = parser.cell_summary("XYZ401")
    assert summary["failure_count"] == len(fails)
    assert summary["ue_count"] >= 10


def test_scenario_mapping_rach():
    parser = UETraceParser()
    fails = parser.failures_for_cell("XYZ401")
    rach = [f for f in fails if f.ue_id == "UE10002"]
    assert len(rach) == 1
    assert rach[0].scenario_key() == "RACH_FAILURE"
    base = build_ue_rca_from_event(rach[0])
    assert base["issue"] == "RACH Failure"
    assert base["protocol_layer"] == "RACH"


def test_confidence_tiers():
    assert compute_ue_confidence(has_ue=True)[0] == 0.60
    assert compute_ue_confidence(has_ue=True, has_gnb=True)[0] == 0.80
    assert compute_ue_confidence(has_ue=True, has_gnb=True, has_pm=True)[0] == 0.90
    assert compute_ue_confidence(has_ue=True, has_gnb=True, has_pm=True, has_rf=True)[0] == 0.95
    assert compute_ue_confidence(
        has_ue=True, has_gnb=True, has_pm=True, has_rf=True, has_transport=True
    )[0] == 0.98


def test_correlate_cell_failures_output_shape():
    results = correlate_cell_ue_failures("XYZ401")
    assert len(results) >= 10
    top = results[0]
    assert top.ue_id
    assert top.cell_id == "XYZ401"
    assert top.issue
    assert top.failure_stage
    assert top.protocol_layer
    assert top.primary_root_cause
    assert top.confidence >= 0.60
    fd = top.to_finding_dict()
    assert fd["category"] == "ue_protocol"
    assert "trace_evidence" in fd["evidence"]


def test_ue_agent_analyze():
    agent = UEProtocolAgent()
    result = agent.analyze({"cell_id": "XYZ401"}, query="UE protocol trace RACH failure XYZ401")
    assert result.findings
    assert "UE Protocol Agent" in result.summary
    categories = {f.category for f in result.findings}
    assert "ue_protocol" in categories


def test_enrich_master_rca_includes_ue_protocol():
    findings = enrich_master_rca([], "XYZ401", "UE protocol trace RACH failure XYZ401", {})
    ids = {f.rule_id for f in findings}
    assert any(r.startswith("ue_protocol_") for r in ids)
    assert "ue_protocol_rca_summary" in ids


def test_filter_by_ue_id():
    results = correlate_cell_ue_failures("XYZ401", ue_id="UE10005")
    assert len(results) == 1
    assert results[0].issue == "HO Failure"
