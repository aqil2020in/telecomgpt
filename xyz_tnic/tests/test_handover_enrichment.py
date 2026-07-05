"""Tests for handover enrichment layer + enriched Handover RCA agent integration."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", str(Path(__file__).resolve().parents[2] / "datasets"))
if not Path(os.environ["TNIC_DATASETS_DIR"]).exists():
    os.environ["TNIC_DATASETS_DIR"] = "/workspace/datasets"

from tnic.datasets.handover_enrichment import (  # noqa: E402
    FAILURE_STAGE_MAP,
    RCA_SCENARIOS,
    aggregate_enriched_kpis,
    classify_rca_scenarios,
    enrich_handover_events,
    write_enriched_handover_csv,
)
from tnic.datasets.kpi_service import compute_cell_kpis
from tnic.datasets.loaders import clear_loader_cache, load_handover_events, load_handover_events_enriched
from tnic.datasets.registry import datasets_dir
from tnic.models.schemas import AnalyzeRequest
from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator
from tnic.rules.ho_rules import HO_RULE_ENGINE

# 12 RCA scenarios -> HO rule IDs exercised when KPIs are aggregated from enriched CSV
RCA_SCENARIO_TO_RULES: dict[str, set[str]] = {
    "handover_preparation_failure": {"ho_prep_failure", "ho_missing_neighbor_enriched"},
    "handover_execution_failure": {"ho_execution_failure", "ho_wrong_cell"},
    "too_early_handover": {"ho_too_early", "ho_mobility_config"},
    "too_late_handover": {"ho_too_late", "ho_mobility_config"},
    "ping_pong_handover": {"ho_ping_pong", "ho_mobility_config", "ho_beam_instability"},
    "missing_neighbor": {"ho_missing_neighbor", "ho_missing_neighbor_enriched"},
    "xn_transport_failure": {"ho_xn_failure", "ho_xn_transport"},
    "post_ho_rlf": {"ho_post_ho_rlf"},
    "coverage_induced_ho_failure": {"ho_coverage_induced", "ho_weak_target_rf"},
    "interference_induced_ho_failure": {"ho_interference_induced"},
    "beam_instability": {"ho_beam_instability"},
    "mobility_configuration_issue": {"ho_mobility_config", "ho_too_early", "ho_too_late", "ho_ping_pong"},
}

ENRICHED_KPI_KEYS = (
    "ho_post_ho_rlf_rate",
    "ho_missing_neighbor_rate",
    "ho_coverage_induced_rate",
    "ho_interference_induced_rate",
    "ho_beam_instability_rate",
    "ho_mobility_config_rate",
    "ho_xn_transport_rate",
)


@pytest.fixture(autouse=True)
def _fresh_loaders():
    clear_loader_cache()
    yield
    clear_loader_cache()


@pytest.fixture
def sample_raw() -> pd.DataFrame:
    return pd.DataFrame([
        {"ue_id": "UE1", "cell_id": "XYZ401", "rsrp": -118, "sinr": 22, "failure_type": "PREP_FAILURE"},
        {"ue_id": "UE2", "cell_id": "XYZ401", "rsrp": -95, "sinr": 8, "failure_type": "SUCCESS"},
        {"ue_id": "UE3", "cell_id": "XYZ402", "rsrp": -112, "sinr": -2, "failure_type": "PING_PONG"},
        {"ue_id": "UE4", "cell_id": "XYZ401", "rsrp": -120, "sinr": 1, "failure_type": "XN_FAILURE"},
        {"ue_id": "UE5", "cell_id": "XYZ401", "rsrp": -115, "sinr": -5, "failure_type": "TOO_LATE_HO"},
        {"ue_id": "UE6", "cell_id": "XYZ407", "rsrp": -76, "sinr": 20, "failure_type": "TOO_EARLY_HO"},
    ])


@pytest.fixture
def enriched_csv_path() -> Path:
    path = datasets_dir() / "handover_events_enriched.csv"
    if not path.exists():
        write_enriched_handover_csv(dest=path)
    return path


# --- Transformation layer ---


def test_original_columns_preserved(sample_raw):
    out = enrich_handover_events(sample_raw)
    for col in ("ue_id", "cell_id", "rsrp", "sinr", "failure_type"):
        assert col in out.columns
        assert out[col].tolist() == sample_raw[col].tolist()


def test_derived_columns_present(sample_raw):
    out = enrich_handover_events(sample_raw)
    required = {
        "timestamp", "source_cell", "target_cell", "serving_rsrp", "target_rsrp",
        "serving_sinr", "target_sinr", "serving_rsrq", "target_rsrq", "event_type",
        "measurement_event", "ho_type", "failure_stage", "speed_kmph", "beam_id",
        "pci_source", "pci_target", "time_to_trigger_ms", "hysteresis_db",
        "xn_latency_ms", "packet_loss_pct", "t310_expiry", "rlf_detected", "result",
        "rca_scenarios",
    }
    assert required.issubset(set(out.columns))


def test_failure_stage_mapping(sample_raw):
    out = enrich_handover_events(sample_raw)
    stages = dict(zip(out["failure_type"], out["failure_stage"]))
    assert stages["PREP_FAILURE"] == FAILURE_STAGE_MAP["PREP_FAILURE"]
    assert stages["PING_PONG"] == "POST_HO"
    assert stages["TOO_LATE_HO"] == "HO_DECISION"
    assert stages["SUCCESS"] == "SUCCESS"


def test_rca_scenario_tags_per_event(sample_raw):
    out = enrich_handover_events(sample_raw)
    prep = out[out["failure_type"] == "PREP_FAILURE"].iloc[0]
    assert "handover_preparation_failure" in classify_rca_scenarios(prep.to_dict())
    xn = out[out["failure_type"] == "XN_FAILURE"].iloc[0]
    assert "xn_transport_failure" in classify_rca_scenarios(xn.to_dict())
    early = out[out["failure_type"] == "TOO_EARLY_HO"].iloc[0]
    tags = classify_rca_scenarios(early.to_dict())
    assert "too_early_handover" in tags
    assert "mobility_configuration_issue" in tags


def test_all_twelve_rca_scenarios_in_full_dataset(enriched_csv_path):
    df = pd.read_csv(enriched_csv_path)
    found: set[str] = set()
    for raw in df["rca_scenarios"].fillna(""):
        for tag in str(raw).split("|"):
            if tag:
                found.add(tag)
    assert len(RCA_SCENARIOS) == 12
    for scenario in RCA_SCENARIOS:
        assert scenario in found, f"missing scenario in enriched data: {scenario}"


def test_loader_enriched_matches_raw_row_count():
    raw = load_handover_events()
    enriched = load_handover_events_enriched()
    assert len(enriched) == len(raw)


# --- KPI + HO agent (enriched RCA path) ---


def test_aggregate_enriched_kpis_xyz401():
    df = load_handover_events_enriched()
    kpis = aggregate_enriched_kpis(df, "XYZ401")
    assert kpis.get("ho_event_count", 0) > 0
    for key in ENRICHED_KPI_KEYS:
        assert key in kpis, f"missing enriched KPI: {key}"


def test_compute_cell_kpis_uses_enriched_source():
    bundle = compute_cell_kpis("XYZ401")
    assert "handover_events_enriched" in bundle.sources
    for key in ENRICHED_KPI_KEYS:
        assert key in bundle.kpis, f"compute_cell_kpis missing {key}"


def test_ho_agent_fires_enriched_rules_on_xyz401():
    from tnic.agents.specialists import HOAgent

    kpis = compute_cell_kpis("XYZ401").kpis
    result = HOAgent().analyze(kpis, query="handover failure cell XYZ401")
    assert result.agent == "ho_agent"
    rule_ids = {f.rule_id for f in result.findings}
    enriched_rules = {
        "ho_prep_failure", "ho_wrong_cell", "ho_coverage_induced",
        "ho_missing_neighbor_enriched", "ho_post_ho_rlf", "ho_mobility_config",
        "ho_xn_transport", "ho_interference_induced",
    }
    assert rule_ids & enriched_rules, f"expected enriched HO rules, got {rule_ids}"


def test_ho_rule_engine_covers_all_rca_scenarios(enriched_csv_path):
    """Each of the 12 RCA scenarios maps to at least one HO rule on demo cells."""
    cells = ["XYZ401", "XYZ407", "XYZ405"]
    fired_rules: set[str] = set()
    for cell in cells:
        kpis = aggregate_enriched_kpis(pd.read_csv(enriched_csv_path), cell)
        if not kpis:
            continue
        fired_rules |= {f["rule_id"] for f in HO_RULE_ENGINE.evaluate(kpis)}

    covered_scenarios: set[str] = set()
    for scenario, rules in RCA_SCENARIO_TO_RULES.items():
        if fired_rules & rules:
            covered_scenarios.add(scenario)

    missing = set(RCA_SCENARIOS) - covered_scenarios
    assert not missing, f"RCA scenarios without matching HO rules on demo cells: {missing}"


# --- Master RCA orchestrator integration ---


def test_master_rca_handover_uses_enriched_kpis():
    orch = MasterRCAOrchestrator()
    result = orch.run(AnalyzeRequest(query="handover failure cell XYZ401"))
    assert result.issue_type == "handover"
    assert "ho_agent" in result.agents_run
    rule_ids = {f.rule_id for f in result.findings}
    assert rule_ids & {
        "ho_prep_failure", "ho_coverage_induced", "ho_missing_neighbor_enriched",
        "ho_post_ho_rlf", "ho_wrong_cell",
    }, f"Master RCA missing enriched HO findings: {rule_ids}"


def test_master_rca_ping_pong_scenario():
    orch = MasterRCAOrchestrator()
    result = orch.run(AnalyzeRequest(query="ping pong handover cell XYZ407"))
    ho_findings = [f for f in result.findings if f.category == "handover"]
    assert ho_findings
    rule_ids = {f.rule_id for f in ho_findings}
    assert "ho_ping_pong" in rule_ids or "ho_mobility_config" in rule_ids


# --- Dashboard path ---


def test_dashboard_handover_df_enriched_columns():
    from dashboard.dashboard_utils import handover_df

    df = handover_df("XYZ401")
    assert len(df) > 0
    assert "failure_stage" in df.columns
    assert "target_cell" in df.columns
    assert "rca_scenarios" in df.columns
    assert "source_cell" in df.columns
