"""Tests for RF Coverage Agent and 3-mile drive-test optimizer."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")


@pytest.fixture
def geo_csv():
    from tnic.services.coverage_optimizer import geospatial_dataset_path

    return geospatial_dataset_path()


def test_geospatial_dataset_exists(geo_csv):
    assert geo_csv.exists()
    assert geo_csv.name == "enhanced_geospatial_rf_dataset.csv"


def test_optimize_coverage_3mi_radius(geo_csv):
    from tnic.services.coverage_optimizer import optimize_coverage

    result = optimize_coverage(geo_csv, radius_miles=3.0)
    assert result["ok"] is True
    assert result["points_in_radius"] > 100
    assert len(result["best_measured"]) >= 5
    assert len(result["drive_route"]) > 50
    assert result["center"]["radius_miles"] == 3.0


def test_google_map_artifact(geo_csv):
    from tnic.services.coverage_google_map import build_coverage_google_map_artifact
    from tnic.services.coverage_optimizer import optimize_coverage

    result = optimize_coverage(geo_csv, radius_miles=3.0)
    artifact = build_coverage_google_map_artifact(result)
    assert artifact is not None
    assert artifact["map_provider"] == "google"
    md = artifact["map_data"]
    assert md["radius_miles"] == 3.0
    assert len(md["drive_route"]) > 0
    assert len(md["best_locations"]) > 0


def test_rf_coverage_agent_diagnosis(geo_csv):
    from tnic.agents.rf_coverage_agent import RFCoverageAgent

    d = RFCoverageAgent().analyze_drive_test(
        query="coverage optimizer 3 mile radius",
        csv_path=geo_csv,
        radius_miles=3.0,
    )
    assert d.issue_class in {"Coverage Hole Cluster", "Weak RF Zones", "Acceptable Coverage"}
    assert d.confidence > 0.5
    assert d.map_artifact is not None
    assert len(d.evidence) >= 3


def test_specialist_wrapper(geo_csv):
    from tnic.agents.specialists import RFCoverageAgent

    r = RFCoverageAgent().analyze({"radius_miles": 3.0}, query="3 mile radius drive test")
    assert r.agent == "rf_coverage_agent"
    assert len(r.findings) == 1
    assert r.findings[0].category == "rf_coverage"


def test_render_maps_html_without_key(geo_csv):
    from tnic.services.coverage_google_map import render_google_maps_html
    from tnic.services.coverage_optimizer import optimize_coverage

    result = optimize_coverage(geo_csv, radius_miles=3.0)
    artifact = result
    from tnic.services.coverage_google_map import build_coverage_google_map_artifact

    md = build_coverage_google_map_artifact(result)["map_data"]
    html = render_google_maps_html(md)
    assert "Google Maps" in html or "map" in html.lower()
