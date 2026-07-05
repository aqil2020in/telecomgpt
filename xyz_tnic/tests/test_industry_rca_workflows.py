"""Tests for industry RCA workflow alignment (Pradeep Dhote framework)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tnic.orchestrator.master_rca import (
    WORKFLOW_CORRELATION_MAP,
    enrich_master_rca,
    workflow_correlation_findings,
)
from tnic.orchestrator.workflow_registry import WORKFLOW_REGISTRY, detect_workflow, workflow_agents
from tnic.rules.anr_rules import ANR_RULE_ENGINE
from tnic.rules.config_audit_rules import CONFIG_AUDIT_RULE_ENGINE
from tnic.rules.gnb_syslog_rules import GNB_SYSLOG_RULE_ENGINE
from tnic.rules.vonr_rules import VONR_RULE_ENGINE
from tnic.services.gnb_syslog_parser import parse_syslog_text


def test_eight_workflows_registered():
    assert len(WORKFLOW_REGISTRY) == 8
    assert "call_drop" in WORKFLOW_REGISTRY
    assert "handover_failure" in WORKFLOW_REGISTRY
    assert "vonr_5g_sa" in WORKFLOW_REGISTRY
    assert "cell_outage" in WORKFLOW_REGISTRY


def test_detect_workflow_call_drop():
    assert detect_workflow("high call drop rate cell XYZ401") == "call_drop"


def test_detect_workflow_vonr():
    assert detect_workflow("VoNR 5QI-1 setup failure") == "vonr_5g_sa"


def test_workflow_agents_handover():
    agents = workflow_agents("handover_failure")
    assert "handover" in agents
    assert "anr" in agents
    assert "gnb_syslog" in agents


def test_vonr_rules_fire():
    kpis = {"vonr_setup_success_rate": 90, "ims_registration_rate": 95}
    findings = VONR_RULE_ENGINE.evaluate(kpis)
    assert any(f["rule_id"] == "vonr_setup_fail" for f in findings)


def test_anr_rules_pci_conflict():
    findings = ANR_RULE_ENGINE.evaluate({"pci_conflict_count": 2})
    assert any(f["rule_id"] == "anr_pci_conflict" for f in findings)


def test_config_audit_drift():
    findings = CONFIG_AUDIT_RULE_ENGINE.evaluate({"ho_a3_offset_db": 12})
    assert any(f["rule_id"] == "cfg_audit_ho_a3_offset_db" for f in findings)


def test_syslog_ngap_signature():
    text = "NGAP HandoverPreparationFailure cause radioNetwork"
    parsed = parse_syslog_text(text)
    assert any(p["rule_id"] == "syslog_ngap_ho_failure" for p in parsed)


def test_syslog_rlf_signature():
    text = "Radio link failure T310 expiry out-of-sync"
    parsed = parse_syslog_text(text)
    assert any(p["rule_id"] == "syslog_rlf_out_of_sync" for p in parsed)


def test_gnb_syslog_agent_engine():
    findings = GNB_SYSLOG_RULE_ENGINE.evaluate({"query": "XnAP failure SCTP timeout"})
    assert len(findings) >= 1
    assert findings[0]["category"] == "gnb_syslog"


def test_workflow_correlation_call_drop():
    findings = workflow_correlation_findings("call drop cell XYZ401", "XYZ401")
    assert any(f.rule_id == "workflow_call_drop" for f in findings)
    assert any(f.rule_id.startswith("workflow_corr_") for f in findings)


def test_workflow_correlation_map_coverage():
    assert "handover_failure" in WORKFLOW_CORRELATION_MAP
    assert "vonr_5g_sa" in WORKFLOW_CORRELATION_MAP


def test_enrich_master_rca_integration():
    findings = enrich_master_rca([], "XYZ401", "call drop handover failure cell XYZ401", {})
    ids = {f.rule_id for f in findings}
    assert any("workflow" in i or "coverage" in i for i in ids)


def test_new_agents_in_registry():
    from tnic.agents.specialists import AGENT_REGISTRY
    for key in ("vonr", "anr", "config_audit", "gnb_syslog"):
        assert key in AGENT_REGISTRY
