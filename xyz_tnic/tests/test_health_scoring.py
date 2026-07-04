"""Health scoring tests."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["APP_ENV"] = "test"

from app.services.health_scoring import compute_health_score
from app.services.pm_ingestion import validate_pm_kpis, ingest_pm_csv


def test_health_score_good():
    h = compute_health_score({
        "ss_sinr": 18, "ss_rsrp": -80, "throughput_mbps": 150,
        "ho_success_rate": 98, "rach_success_rate": 99, "call_drop_rate": 0.5,
    })
    assert h["overall_score"] >= 80
    assert h["grade"] in ("A", "B")


def test_health_score_poor():
    h = compute_health_score({
        "ss_sinr": 2, "call_drop_rate": 5, "ho_success_rate": 88,
        "throughput_mbps": 15, "beam_failure_ratio": 35,
    })
    assert h["overall_score"] < 70
    assert len(h["alerts"]) >= 1


def test_pm_validation():
    issues = validate_pm_kpis({"cqi": 20, "ss_rsrp": 5})
    assert len(issues) >= 2


def test_pm_ingest_sample():
    sample = Path(__file__).resolve().parent.parent / "data" / "samples" / "pm_counters_sample.csv"
    if sample.exists():
        result = ingest_pm_csv(sample)
        assert result["ok"]
        assert result["rows_ingested"] > 0
        assert "43211" in result["cells"]


if __name__ == "__main__":
    test_health_score_good()
    test_health_score_poor()
    test_pm_validation()
    test_pm_ingest_sample()
    print("Health/PM tests passed.")
