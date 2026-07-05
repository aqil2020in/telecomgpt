"""Tests for handover event enrichment layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tnic.datasets.handover_enrichment import (
    FAILURE_STAGE_MAP,
    RCA_SCENARIOS,
    aggregate_enriched_kpis,
    classify_rca_scenarios,
    enrich_handover_events,
    write_enriched_handover_csv,
)
from tnic.datasets.loaders import load_handover_events, load_handover_events_enriched
from tnic.rules.ho_rules import HO_RULE_ENGINE


@pytest.fixture
def sample_raw() -> pd.DataFrame:
    return pd.DataFrame([
        {"ue_id": "UE1", "cell_id": "XYZ401", "rsrp": -118, "sinr": 22, "failure_type": "PREP_FAILURE"},
        {"ue_id": "UE2", "cell_id": "XYZ401", "rsrp": -95, "sinr": 8, "failure_type": "SUCCESS"},
        {"ue_id": "UE3", "cell_id": "XYZ402", "rsrp": -112, "sinr": -2, "failure_type": "PING_PONG"},
        {"ue_id": "UE4", "cell_id": "XYZ401", "rsrp": -120, "sinr": 1, "failure_type": "XN_FAILURE"},
    ])


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
    }
    assert required.issubset(set(out.columns))


def test_failure_stage_mapping(sample_raw):
    out = enrich_handover_events(sample_raw)
    stages = dict(zip(out["failure_type"], out["failure_stage"]))
    assert stages["PREP_FAILURE"] == FAILURE_STAGE_MAP["PREP_FAILURE"]
    assert stages["PING_PONG"] == "POST_HO"
    assert stages["SUCCESS"] == "SUCCESS"


def test_rca_scenario_tags(sample_raw):
    out = enrich_handover_events(sample_raw)
    prep = out[out["failure_type"] == "PREP_FAILURE"].iloc[0]
    tags = classify_rca_scenarios(prep.to_dict())
    assert "handover_preparation_failure" in tags
    xn = out[out["failure_type"] == "XN_FAILURE"].iloc[0]
    assert "xn_transport_failure" in classify_rca_scenarios(xn.to_dict())


def test_all_rca_scenarios_reachable_in_full_dataset():
    path = Path("/workspace/datasets/handover_events_enriched.csv")
    if not path.exists():
        write_enriched_handover_csv(dest=path)
    df = pd.read_csv(path)
    found: set[str] = set()
    for raw in df["rca_scenarios"].fillna(""):
        for tag in str(raw).split("|"):
            if tag:
                found.add(tag)
    for scenario in RCA_SCENARIOS:
        assert scenario in found, f"missing scenario in enriched data: {scenario}"


def test_aggregate_enriched_kpis():
    df = load_handover_events_enriched()
    kpis = aggregate_enriched_kpis(df, "XYZ401")
    assert kpis.get("ho_event_count", 0) > 0
    assert "ho_post_ho_rlf_rate" in kpis
    assert "ho_coverage_induced_rate" in kpis


def test_ho_rules_fire_on_enriched_kpis():
    df = load_handover_events_enriched()
    kpis = aggregate_enriched_kpis(df, "XYZ401")
    findings = HO_RULE_ENGINE.evaluate(kpis)
    assert isinstance(findings, list)
    rule_ids = {f["rule_id"] for f in findings}
    # At least one enriched rule or classic HO rule should fire for demo cell
    assert rule_ids & {
        "ho_prep_failure", "ho_wrong_cell", "ho_coverage_induced",
        "ho_missing_neighbor_enriched", "ho_ping_pong",
    }


def test_loader_enriched_matches_raw_row_count():
    raw = load_handover_events()
    enriched = load_handover_events_enriched()
    assert len(enriched) == len(raw)
