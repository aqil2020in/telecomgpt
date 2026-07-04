"""Tests for the PM Validation Agent."""

from __future__ import annotations

import os

import pandas as pd
import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")


@pytest.fixture(autouse=True)
def _clear_loader_cache():
    from tnic.datasets.loaders import clear_loader_cache

    clear_loader_cache()
    yield
    clear_loader_cache()


@pytest.fixture
def agent():
    from tnic.agents.pm_validation_agent import PMValidationAgent

    return PMValidationAgent()


def test_anomaly_report_schema(agent):
    from tnic.agents.pm_validation_agent import generate_pm_anomaly_report

    report = generate_pm_anomaly_report(cell_id="XYZ401")
    assert "ok" in report
    assert "summary" in report
    assert "anomalies" in report
    assert "checks_passed" in report
    assert set(report["checks_passed"].keys()) >= {"ho_balance", "rach_balance", "rrc_balance"}


def test_demo_dataset_passes_validation(agent):
    report = agent.analyze(cell_id="XYZ401")
    assert report.ok is True
    assert report.anomaly_count == 0
    assert report.checks_passed["ho_balance"] is True
    assert report.checks_passed["rach_balance"] is True
    assert report.checks_passed["rrc_balance"] is True


def test_validate_ho_balance_ok():
    from tnic.agents.pm_validation_agent import validate_ho_balance

    assert validate_ho_balance(100, 80, 20) is None
    assert validate_ho_balance(100, 80, None) is None


def test_validate_ho_balance_fail():
    from tnic.agents.pm_validation_agent import validate_ho_balance

    issue = validate_ho_balance(100, 90, 5)
    assert issue is not None
    assert issue.rule_id == "HO_BALANCE"


def test_validate_rach_balance_fail():
    from tnic.agents.pm_validation_agent import validate_rach_balance

    issue = validate_rach_balance(50, 60)
    assert issue is not None
    assert issue.rule_id == "RACH_BALANCE"


def test_validate_rrc_balance_fail():
    from tnic.agents.pm_validation_agent import validate_rrc_balance

    issue = validate_rrc_balance(30, 40)
    assert issue is not None
    assert issue.rule_id == "RRC_BALANCE"


def test_dataframe_detects_ho_anomaly(agent):
    pm = pd.DataFrame([{
        "cell_id": "T1",
        "ho_attempt": 100,
        "ho_success": 90,
        "ho_failure": 5,
        "rach_attempt": 50,
        "rach_success": 40,
    }])
    report = agent.analyze(cell_id="T1", pm=pm)
    assert report.ok is False
    assert any(a.rule_id == "HO_BALANCE" for a in report.anomalies)


def test_dataframe_detects_rach_anomaly(agent):
    pm = pd.DataFrame([{
        "cell_id": "T2",
        "ho_attempt": 100,
        "ho_success": 80,
        "rach_attempt": 40,
        "rach_success": 45,
    }])
    report = agent.analyze(cell_id="T2", pm=pm)
    assert report.ok is False
    assert any(a.rule_id == "RACH_BALANCE" for a in report.anomalies)


def test_dataframe_detects_rrc_anomaly(agent):
    pm = pd.DataFrame([{
        "cell_id": "T3",
        "ho_attempt": 100,
        "ho_success": 80,
        "rach_attempt": 50,
        "rach_success": 40,
        "rrc_attempt": 30,
        "rrc_success": 35,
    }])
    report = agent.analyze(cell_id="T3", pm=pm)
    assert report.ok is False
    assert any(a.rule_id == "RRC_BALANCE" for a in report.anomalies)


def test_derive_rrc_counters_when_missing():
    from tnic.agents.pm_validation_agent import derive_rrc_counters

    att, succ = derive_rrc_counters({
        "rach_attempt": 100,
        "rach_success": 80,
        "ho_attempt": 200,
        "ho_success": 150,
    })
    assert att >= succ


def test_specialist_wrapper_with_cell_id():
    from tnic.agents.specialists import PMAgent

    result = PMAgent().analyze({"cell_id": "XYZ401"})
    assert result.agent == "pm_agent"
    assert "passed" in result.summary.lower() or result.summary


def test_specialist_wrapper_kpi_fallback(degraded_kpis):
    from tnic.agents.specialists import PMAgent

    kpis = {**degraded_kpis, "cqi": 20}
    result = PMAgent().analyze(kpis)
    assert result.agent == "pm_agent"
    assert len(result.findings) >= 1


def test_analyze_kpis_with_raw_counters(agent):
    report = agent.analyze_kpis({
        "cell_id": "T4",
        "ho_attempt": 200,
        "ho_success": 160,
        "rach_attempt": 100,
        "rach_success": 90,
    })
    assert report.ok is True
    assert report.metrics["ho_failure"] == 40
