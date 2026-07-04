"""PM ingestion tests."""

from __future__ import annotations

from tnic.services.pm_ingestion import aggregate_cell_kpis, ingest_pm_csv, validate_pm_kpis


def test_aggregate_cell_kpis(pm_csv_path):
    agg = aggregate_cell_kpis(pm_csv_path)
    assert "43211" in agg
    assert "ho_success_rate" in agg["43211"]
    assert agg["43211"]["ho_success_rate"] == 91.2


def test_validate_pm_kpis_detects_bad_cqi():
    issues = validate_pm_kpis({"cqi": 20})
    assert any("CQI" in i for i in issues)


def test_ingest_pm_csv(pm_csv_path):
    result = ingest_pm_csv(pm_csv_path)
    assert result["ok"] is True
    assert result["rows_ingested"] >= 20
    assert "43211" in result["cells"]
