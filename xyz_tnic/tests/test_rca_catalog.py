"""Tests for 28-type RCA catalog."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tnic.orchestrator.master_rca import enrich_master_rca, rca_catalog_findings
from tnic.orchestrator.rca_catalog import RCA_CATALOG, detect_rca_type, list_rca_types, rca_agents
from tnic.rules.alarm_rules import ALARM_RULE_ENGINE
from tnic.rules.core_rules import CORE_RULE_ENGINE
from tnic.rules.coverage_rules import COVERAGE_RULE_ENGINE
from tnic.rules.pm_validation_rules import PM_VALIDATION_RULE_ENGINE
from tnic.rules.transport_rules import TRANSPORT_RULE_ENGINE
from tnic.rules.vonr_rules import VONR_RULE_ENGINE


EXPECTED_RCA_TYPES = [
    "coverage_hole",
    "overshooting_cell",
    "pilot_pollution",
    "interference",
    "ho_prep_failure",
    "ho_execution_failure",
    "ping_pong",
    "too_early_ho",
    "too_late_ho",
    "rlf",
    "rrc_setup_failure",
    "rach_failure",
    "vonr_drop",
    "pdu_session_failure",
    "beam_failure",
    "low_throughput",
    "latency",
    "anr_failure",
    "neighbor_missing",
    "pci_conflict",
    "configuration_drift",
    "scheduler_congestion",
    "transport_congestion",
    "xn_failure",
    "ng_n2_failure",
    "pm_counter_integrity",
    "alarm_correlation",
    "syslog_correlation",
]


def test_all_28_rca_types_registered():
    assert len(RCA_CATALOG) == 28
    for key in EXPECTED_RCA_TYPES:
        assert key in RCA_CATALOG, f"Missing RCA type: {key}"


def test_list_rca_types():
    items = list_rca_types()
    assert len(items) == 28
    assert all("title" in i and "agents" in i for i in items)


def test_detect_rca_type_coverage_hole():
    assert detect_rca_type("coverage hole at cell edge XYZ401") == "coverage_hole"


def test_detect_rca_type_ping_pong():
    assert detect_rca_type("ping pong handover between neighbors") == "ping_pong"


def test_detect_rca_type_syslog():
    assert detect_rca_type("gnb syslog correlation NGAP failure") == "syslog_correlation"


def test_rca_agents_ho_prep():
    agents = rca_agents("ho_prep_failure")
    assert "handover" in agents
    assert "anr" in agents


def test_coverage_hole_rule_fires():
    findings = COVERAGE_RULE_ENGINE.evaluate({"ss_rsrp": -115})
    assert any(f["rule_id"] == "cov_coverage_hole" for f in findings)


def test_overshooting_rule_fires():
    findings = COVERAGE_RULE_ENGINE.evaluate({"distance_miles": 3.0, "ss_rsrp": -88})
    assert any(f["rule_id"] == "cov_overshooting" for f in findings)


def test_pilot_pollution_rule_fires():
    findings = COVERAGE_RULE_ENGINE.evaluate({"ss_rsrp": -92, "ss_sinr": -2})
    assert any(f["rule_id"] == "cov_pilot_pollution" for f in findings)


def test_interference_rule_fires():
    findings = COVERAGE_RULE_ENGINE.evaluate({"ss_rsrp": -95, "ss_sinr": -6})
    assert any(f["rule_id"] == "cov_interference" for f in findings)


def test_transport_congestion_rule():
    findings = TRANSPORT_RULE_ENGINE.evaluate({"backhaul_utilization": 85})
    assert any(f["rule_id"] == "transport_congestion" for f in findings)


def test_pdu_session_failure_rule():
    findings = CORE_RULE_ENGINE.evaluate({"pdu_session_fail_rate": 5})
    assert any(f["rule_id"] == "core_pdu_session_fail" for f in findings)


def test_ng_n2_failure_rule():
    findings = CORE_RULE_ENGINE.evaluate({"ho_n2_fail_rate": 5})
    assert any(f["rule_id"] == "core_ng_n2_failure" for f in findings)


def test_vonr_drop_rule():
    findings = VONR_RULE_ENGINE.evaluate({"vonr_drop_rate": 3})
    assert any(f["rule_id"] == "vonr_drop" for f in findings)


def test_pm_integrity_rule():
    findings = PM_VALIDATION_RULE_ENGINE.evaluate({"cqi": 20})
    assert any("cqi" in f["probable_cause"].lower() for f in findings)


def test_alarm_correlation_rule():
    findings = ALARM_RULE_ENGINE.evaluate({"active_alarm_count": 2, "call_drop_rate": 5})
    assert any(f["rule_id"] == "alarm_kpi_correlation" for f in findings)


def test_rca_catalog_findings_rlf():
    findings = rca_catalog_findings("RLF radio link failure T310", "XYZ401")
    assert any(f.rule_id == "rca_catalog_rlf" for f in findings)


def test_enrich_master_rca_with_catalog():
    findings = enrich_master_rca([], "XYZ401", "PCI conflict mod-3 collision XYZ401", {})
    ids = {f.rule_id for f in findings}
    assert any("rca_catalog" in i for i in ids)


def test_each_rca_has_required_fields():
    for key, spec in RCA_CATALOG.items():
        assert spec.get("title"), key
        assert spec.get("domains"), key
        assert spec.get("agents"), key
        assert spec.get("rule_ids"), key
        assert spec.get("recommended_fixes"), key
