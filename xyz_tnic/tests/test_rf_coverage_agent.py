"""Tests for RF Coverage Agent — telecom rules, scoring, hotspots, APIs, Master RCA."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from agents.rf_coverage_agent import (  # noqa: E402
    CoverageScoreCalculator,
    RFCoverageAgent,
    analyze_rf_coverage,
    build_hotspots_df,
    classify_row,
    detect_beam_coverage_gaps,
    detect_cell_edge_regions,
    detect_coverage_holes,
    detect_interference_regions,
    detect_latency_hotspots,
    geospatial_dataset_path,
    load_geospatial_df,
)
from tnic.agents.specialists import RFCoverageAgent as SpecialistRFCoverageAgent  # noqa: E402
from tnic.main import create_app  # noqa: E402
from tnic.orchestrator.master_rca import COVERAGE_CORRELATION_MAP, enrich_rca_with_coverage  # noqa: E402


@pytest.fixture(scope="module")
def geo_csv():
    path = geospatial_dataset_path()
    assert path.exists()
    return path


@pytest.fixture(scope="module")
def geo_df(geo_csv):
    return load_geospatial_df(geo_csv)


@pytest.fixture(scope="module")
def agent(geo_csv):
    return RFCoverageAgent(csv_path=geo_csv)


def test_geospatial_dataset_loads(geo_df):
    assert len(geo_df) > 500
    required = {
        "timestamp", "ue_id", "latitude", "longitude", "cell_id", "rsrp_dbm",
        "sinr_db", "bler_dl_pct", "dl_tp_mbps", "latency_ms", "beam_health_score",
    }
    assert required.issubset(set(geo_df.columns))


def test_classify_row_telecom_rules():
    hole = pd.Series({"rsrp_dbm": -118, "sinr_db": 2, "bler_dl_pct": 5, "dl_tp_mbps": 150, "latency_ms": 40})
    assert "COVERAGE_HOLE" in classify_row(hole)

    weak = pd.Series({"rsrp_dbm": -108, "sinr_db": 2, "bler_dl_pct": 5, "dl_tp_mbps": 150, "latency_ms": 40})
    assert "WEAK_COVERAGE" in classify_row(weak)
    assert "COVERAGE_HOLE" not in classify_row(weak)

    interference = pd.Series({"rsrp_dbm": -95, "sinr_db": -6, "bler_dl_pct": 5, "dl_tp_mbps": 150, "latency_ms": 40})
    assert "INTERFERENCE" in classify_row(interference)

    bler = pd.Series({"rsrp_dbm": -95, "sinr_db": 10, "bler_dl_pct": 12, "dl_tp_mbps": 150, "latency_ms": 40})
    assert "HIGH_BLER" in classify_row(bler)

    tp = pd.Series({"rsrp_dbm": -95, "sinr_db": 10, "bler_dl_pct": 2, "dl_tp_mbps": 80, "latency_ms": 40})
    assert "LOW_THROUGHPUT" in classify_row(tp)

    lat = pd.Series({"rsrp_dbm": -95, "sinr_db": 10, "bler_dl_pct": 2, "dl_tp_mbps": 200, "latency_ms": 95})
    assert "LATENCY_HOTSPOT" in classify_row(lat)


def test_coverage_score_calculator_weights():
    calc = CoverageScoreCalculator()
    assert calc.WEIGHTS["rsrp"] == 0.35
    assert calc.WEIGHTS["sinr"] == 0.25
    assert calc.WEIGHTS["throughput"] == 0.15
    assert calc.WEIGHTS["bler"] == 0.15
    assert calc.WEIGHTS["latency"] == 0.10
    good = pd.Series({"rsrp_dbm": -82, "sinr_db": 18, "dl_tp_mbps": 450, "bler_dl_pct": 1, "latency_ms": 25})
    bad = pd.Series({"rsrp_dbm": -118, "sinr_db": -8, "dl_tp_mbps": 40, "bler_dl_pct": 18, "latency_ms": 120})
    assert calc.row_score(good) > calc.row_score(bad)


def test_xyz401_demo_targets(agent):
    summary = agent.analyze_cell("XYZ401")
    assert summary.primary_issue == "Coverage Deficiency"
    assert summary.secondary_issue == "Beam Congestion"
    assert summary.coverage_score == 52
    assert summary.confidence == 0.94
    impacts = set(summary.impacts)
    assert "HO Failures" in impacts
    assert "RLF" in impacts
    assert "Call Drops" in impacts
    assert "RACH Failures" in impacts
    assert "Low Throughput" in impacts


def test_analyze_rf_coverage_helper(agent):
    result = analyze_rf_coverage("XYZ401", csv_path=agent.csv_path)
    assert result["cell_id"] == "XYZ401"
    assert result["coverage_score"] == 52
    assert "primary_issue" in result
    assert "recommendation" in result


def test_hotspot_detectors(geo_df):
    holes = detect_coverage_holes(geo_df)
    assert not holes.empty
    assert holes["hotspot_type"].eq("coverage_hole").all()

    interference = detect_interference_regions(geo_df)
    if not interference.empty:
        assert (interference["sinr_db"] <= -5).all()

    edges = detect_cell_edge_regions(geo_df)
    if not edges.empty:
        assert (edges["distance_miles"] >= 2.2).all()

    latency = detect_latency_hotspots(geo_df)
    if not latency.empty:
        assert (latency["latency_ms"] > 80).all()

    beams = detect_beam_coverage_gaps(geo_df)
    assert beams.empty or "hotspot_type" in beams.columns


def test_build_hotspots_csv(agent, tmp_path):
    out = agent.generate_coverage_hotspots_csv(tmp_path / "coverage_hotspots.csv")
    assert out.exists()
    df = pd.read_csv(out)
    assert "hotspot_type" in df.columns
    assert len(df) > 0


def test_coverage_summary_json(agent, tmp_path):
    out = agent.generate_coverage_summary_json(tmp_path / "coverage_summary.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "cells" in payload
    assert len(payload["cells"]) >= 3
    xyz401 = next(c for c in payload["cells"] if c["cell_id"] == "XYZ401")
    assert xyz401["coverage_score"] == 52
    assert xyz401["primary_issue"] == "Coverage Deficiency"


def test_specialist_wrapper(agent):
    result = SpecialistRFCoverageAgent().analyze({"cell_id": "XYZ401"}, query="coverage hole XYZ401")
    assert result.agent == "rf_coverage_agent"
    assert len(result.findings) >= 1
    assert result.findings[0].category == "rf_coverage"
    assert "Coverage Deficiency" in result.findings[0].probable_cause


def test_master_rca_coverage_correlation():
    assert "COVERAGE_HOLE" in COVERAGE_CORRELATION_MAP
    impacts = {item["impact"] for item in COVERAGE_CORRELATION_MAP["COVERAGE_HOLE"]}
    assert "HO Failure" in impacts
    assert "RLF" in impacts
    assert "Call Drops" in impacts
    assert "RACH Failure" in impacts
    assert "Throughput Degradation" in impacts
    assert "Customer Complaints" in impacts


def test_enrich_rca_with_coverage():
    enriched = enrich_rca_with_coverage([], cell_id="XYZ401")
    assert any(f.rule_id == "rf_coverage_primary" for f in enriched)
    assert any(f.rule_id.startswith("coverage_corr_") for f in enriched)


def test_coverage_api_routes():
    app = create_app()
    client = TestClient(app)

    from tnic.config import get_settings
    prefix = get_settings().api_prefix

    post = client.post(f"{prefix}/analyze-coverage", json={"cell_id": "XYZ401", "write_outputs": False})
    assert post.status_code == 200
    body = post.json()
    assert body["ok"] is True
    assert body["cell_id"] == "XYZ401"
    assert body["coverage_score"] == 52

    summary = client.get(f"{prefix}/coverage-summary", params={"cell_id": "XYZ401"})
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["primary_issue"] == "Coverage Deficiency"

    hotspots = client.get(f"{prefix}/coverage-hotspots", params={"cell_id": "XYZ401", "limit": 50})
    assert hotspots.status_code == 200
    assert hotspots.json()["count"] > 0


def test_detect_issue_type_rf_coverage():
    from tnic.rules import detect_issue_type

    assert detect_issue_type("RSRP coverage hole on XYZ401", explicit="rf_coverage") == "rf_coverage"
    assert detect_issue_type("geospatial drive test weak coverage", None) == "rf_coverage"
