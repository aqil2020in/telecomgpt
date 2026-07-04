"""Tests for HO, RLF, and Call Drop agent fixes."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")


@pytest.fixture(autouse=True)
def _clear_loader_cache():
    from tnic.datasets.loaders import clear_loader_cache

    clear_loader_cache()
    yield
    clear_loader_cache()


def test_handover_kpis_include_new_failure_rates():
    from tnic.datasets.kpi_service import compute_cell_kpis

    kpis = compute_cell_kpis("XYZ401").kpis
    assert kpis.get("ho_exec_fail_rate") is not None or kpis.get("ho_xn_fail_rate") is not None
    assert "ho_too_early_rate" in kpis
    assert "ho_xn_fail_rate" in kpis
    assert "ho_n2_fail_rate" in kpis


def test_rlf_kpis_fixed():
    from tnic.datasets.kpi_service import compute_cell_kpis

    kpis = compute_cell_kpis("XYZ401").kpis
    assert kpis["rlf_rate"] <= 100
    assert kpis["rlf_rate"] > 0
    assert kpis.get("rlf_after_ho_rate") is not None
    assert kpis.get("rlf_rsrp_mean") is not None
    assert kpis.get("out_of_sync_events", 0) >= 0


def test_rlf_agent_fires_on_xyz401():
    from tnic.agents.specialists import RLFAgent
    from tnic.datasets.kpi_service import compute_cell_kpis

    result = RLFAgent().analyze(compute_cell_kpis("XYZ401").kpis)
    assert len(result.findings) >= 1


def test_call_drop_kpis_and_classification():
    from tnic.datasets.kpi_service import compute_cell_kpis
    from tnic.services.drop_classifier import classify_drop_causes

    kpis = compute_cell_kpis("XYZ401").kpis
    assert kpis["call_drop_rate"] > 2
    assert kpis.get("ims_drop_rate") == kpis.get("drop_ims_pct")
    clf = classify_drop_causes(kpis)
    assert clf["primary"] in {"Mobility", "IMS", "Radio", "Core", "Transport"}


def test_call_drop_agent_fires_on_xyz401():
    from tnic.agents.specialists import CallDropAgent
    from tnic.datasets.kpi_service import compute_cell_kpis

    result = CallDropAgent().analyze(compute_cell_kpis("XYZ401").kpis)
    assert len(result.findings) >= 1


def test_call_drop_rca_uses_drop_not_ho_root_cause():
    from tnic.models.schemas import AnalyzeRequest
    from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator

    result = MasterRCAOrchestrator().run(
        AnalyzeRequest(query="Root cause analysis call drop cell XYZ401")
    )
    assert result.issue_type == "call_drop"
    assert any(f.category == "call_drop" for f in result.findings)
    assert result.probable_root_causes[0]["category"] == "call_drop"


@pytest.mark.parametrize("rule_id,kpis", [
    ("ho_xn_failure", {"ho_xn_fail_rate": 5.0}),
    ("ho_n2_failure", {"ho_n2_fail_rate": 5.0}),
    ("rlf_after_ho", {"rlf_after_ho_rate": 20.0}),
    ("drop_ims", {"drop_ims_pct": 25.0}),
    ("drop_transport", {"drop_transport_pct": 15.0}),
])
def test_individual_rules_fire(rule_id, kpis):
    from tnic.rules import RULE_ENGINES

    engine = None
    for eng in RULE_ENGINES.values():
        if any(r.rule_id == rule_id for r in eng.rules):
            engine = eng
            break
    assert engine is not None
    findings = engine.evaluate(kpis)
    assert any(f["rule_id"] == rule_id for f in findings)
