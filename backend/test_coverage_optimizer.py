"""Tests for coverage optimizer agent."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics.coverage_optimizer import (
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    explain_coverage_optimizer,
    haversine_miles,
    looks_like_coverage_optimizer_query,
    optimize_coverage,
    parse_geo_from_query,
)


SAMPLE = Path(__file__).resolve().parent / "data" / "samples" / "coverage_dallas_3mi.csv"


def test_haversine_zero():
    assert haversine_miles(32.0, -96.0, 32.0, -96.0) == 0.0


def test_parse_geo_from_query():
    lat, lon, r = parse_geo_from_query(
        "Coverage optimizer 32.93704401921274, -96.98407174060758 in 3 miles radius"
    )
    assert abs(lat - 32.93704401921274) < 1e-6
    assert abs(lon - (-96.98407174060758)) < 1e-6
    assert r == 3.0


def test_detector():
    assert looks_like_coverage_optimizer_query(
        "32.937044, -96.984071 3 mile radius best coverage locations"
    )
    assert looks_like_coverage_optimizer_query("coverage optimizer recommend location")


def test_optimize_sample_csv():
    assert SAMPLE.exists(), f"Missing sample {SAMPLE}"
    result = optimize_coverage(
        str(SAMPLE),
        center_lat=DEFAULT_CENTER_LAT,
        center_lon=DEFAULT_CENTER_LON,
        radius_miles=3.0,
    )
    assert result["ok"] is True
    assert result["points_in_radius"] >= 20
    assert len(result["best_measured"]) >= 5
    top = result["best_measured"][0]
    assert top["rf_score"] >= 70
    assert "latitude" in top and "longitude" in top


def test_report_markdown():
    md = explain_coverage_optimizer(
        "32.93704401921274, -96.98407174060758 3 mile radius best coverage",
        csv_path=str(SAMPLE),
    )
    assert "Coverage optimizer report" in md
    assert "Top locations" in md
    assert "32.937" in md


def test_instant_path():
    from telecom_ai.core import TelecomAI

    db = Path(__file__).resolve().parent / "data" / "telecom_master_db.json"
    ai = TelecomAI(db_path=str(db))
    out = ai.run_fast(
        "Coverage optimizer 32.93704401921274, -96.98407174060758 3 miles radius best locations"
    )
    assert out.get("mode") == "fast-kb"
    assert "Top locations" in (out.get("answer") or "")


if __name__ == "__main__":
    tests = [
        test_haversine_zero,
        test_parse_geo_from_query,
        test_detector,
        test_optimize_sample_csv,
        test_report_markdown,
        test_instant_path,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("All coverage optimizer tests passed.")
