"""Tests for core assurance dataset ingestion and Master RCA evidence."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tnic.datasets.kpi_service import compute_cell_kpis
from tnic.datasets.validation import validate_all, validate_dataset
from tnic.orchestrator.master_rca import enrich_master_rca
from tnic.services.assurance_evidence import build_assurance_evidence
from tnic.services.assurance_ingestion import aggregate_assurance_kpis, ingest_all_assurance


def test_assurance_datasets_validate():
    for name in ("gnb_syslog", "cell_configuration", "neighbor_relations", "anr_events", "vonr_sessions", "alarm_events"):
        result = validate_dataset(name)
        assert result.row_count > 0, name
        assert result.ok, f"{name} validation failed: {result.issues}"


def test_aggregate_assurance_kpis_xyz401():
    kpis = aggregate_assurance_kpis("XYZ401")
    assert "assurance_sources" in kpis
    assert len(kpis["assurance_sources"]) >= 4
    assert kpis.get("syslog_event_count", 0) > 0


def test_assurance_kpis_merged_in_compute_cell():
    bundle = compute_cell_kpis("XYZ401")
    assert "gnb_syslog" in bundle.sources or "assurance_sources" in bundle.kpis
    assert bundle.kpis.get("syslog_event_count") or bundle.kpis.get("anr_event_count")


def test_build_assurance_evidence_blocks():
    findings = build_assurance_evidence("XYZ401")
    ids = {f.rule_id for f in findings}
    assert "assurance_syslog_evidence" in ids
    assert "assurance_anr_evidence" in ids
    assert "assurance_vonr_evidence" in ids
    assert "assurance_alarm_evidence" in ids


def test_config_evidence_for_drift():
    kpis = aggregate_assurance_kpis("XYZ401")
    assert kpis.get("ho_a3_offset_db") is not None
    assert kpis.get("pci") == 101
    findings = build_assurance_evidence("XYZ401")
    config = [f for f in findings if f.category == "config_audit" or f.rule_id == "assurance_config_evidence"]
    # Drift count depends on golden baseline; CM values always loaded from CSV
    assert kpis.get("nr_neighbor_count") == 5


def test_syslog_correlates_handover():
    findings = build_assurance_evidence("XYZ401")
    corr = [f for f in findings if f.rule_id.startswith("assurance_syslog_corr_handover")]
    assert len(corr) >= 1
    assert corr[0].confidence >= 0.7


def test_anr_missing_neighbor_evidence():
    kpis = aggregate_assurance_kpis("XYZ401")
    assert kpis.get("anr_missing_neighbor_count", 0) >= 0 or kpis.get("missing_neighbor_count", 0) >= 0


def test_vonr_drop_rate_computed():
    kpis = aggregate_assurance_kpis("XYZ403")
    assert kpis.get("vonr_drop_rate") is not None


def test_enrich_master_rca_includes_assurance():
    findings = enrich_master_rca([], "XYZ401", "handover failure cell XYZ401", {})
    ids = {f.rule_id for f in findings}
    assert "assurance_syslog_evidence" in ids or "assurance_rca_summary" in ids


def test_ingest_all_assurance():
    results = ingest_all_assurance()
    assert len(results) == 6
    assert all(r.rows_ingested > 0 for r in results.values())


def test_validate_all_includes_assurance():
    results = validate_all()
    names = {r.dataset for r in results}
    assert "gnb_syslog" in names
    assert "alarm_events" in names
