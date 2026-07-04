"""Tests for OpenAI RCA Narrator / report_generator."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")
os.environ.setdefault("OPENAI_API_KEY", "")


@pytest.fixture
def sample_rca():
    from tnic.models.schemas import RCAResponse, RuleFinding

    findings = [
        RuleFinding(
            rule_id="ho_prep_failure",
            category="handover",
            probable_cause="High HO preparation failure — Xn interface timeout",
            confidence=0.82,
            evidence={"ho_prep_fail_rate": 9.41, "cell_id": "XYZ401"},
            recommended_actions=["Check Xn transport", "Verify target cell readiness"],
        ),
        RuleFinding(
            rule_id="rlf_coverage",
            category="rlf",
            probable_cause="Coverage hole — RSRP below threshold",
            confidence=0.78,
            evidence={"rlf_rsrp_mean": -112.0},
            recommended_actions=["Adjust tilt", "Add small cell"],
        ),
    ]
    return RCAResponse(
        issue_type="handover",
        query="handover failure cell XYZ401",
        agents_run=["ho_agent", "rlf_agent"],
        findings=findings,
        probable_root_causes=[
            {"cause": findings[0].probable_cause, "confidence": 0.82, "category": "handover"},
        ],
        recommended_actions=["Check Xn transport", "Verify target cell readiness"],
        validation_checklist=["HO success rate restored to SLA"],
        health_score=62.5,
    )


@pytest.fixture
def sample_kpis():
    return {
        "cell_id": "XYZ401",
        "ho_prep_fail_rate": 9.41,
        "ho_success_rate": 78.2,
        "ss_rsrp": -105.0,
        "ss_sinr": 4.5,
    }


def test_narrate_master_rca_schema(sample_rca, sample_kpis):
    from tnic.services.report_generator import narrate_master_rca

    report = narrate_master_rca(sample_rca, kpis=sample_kpis)
    assert report.executive_summary
    assert report.root_cause
    assert len(report.evidence) >= 1
    assert len(report.recommendations) >= 1
    assert 0.0 <= report.confidence <= 1.0
    assert report.source == "template"


def test_structured_report_fields(sample_rca, sample_kpis):
    from tnic.services.report_generator import generate_structured_report

    report = generate_structured_report(rca=sample_rca, kpis=sample_kpis)
    data = report.model_dump()
    assert set(data.keys()) >= {
        "executive_summary",
        "root_cause",
        "evidence",
        "recommendations",
        "confidence",
    }


def test_to_markdown_sections(sample_rca, sample_kpis):
    from tnic.services.report_generator import narrate_master_rca

    md = narrate_master_rca(sample_rca, kpis=sample_kpis).to_markdown()
    for section in (
        "## Executive Summary",
        "## Root Cause",
        "## Evidence",
        "## Recommendations",
        "## Confidence",
    ):
        assert section in md


def test_generate_narrative_report_backward_compat(sample_rca, sample_kpis):
    from tnic.services.report_generator import generate_narrative_report

    md = generate_narrative_report(
        issue_type=sample_rca.issue_type,
        query=sample_rca.query,
        findings=sample_rca.findings,
        kpis=sample_kpis,
    )
    assert "## Executive Summary" in md
    assert "## Root Cause" in md


def test_orchestrator_generates_structured_narrative():
    from tnic.models.schemas import AnalyzeRequest
    from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator

    result = MasterRCAOrchestrator().run(
        AnalyzeRequest(
            query="handover failure cell XYZ401",
            generate_report=True,
        )
    )
    assert result.narrative_report is not None
    assert result.narrative_structured is not None
    assert result.narrative_structured.root_cause
    assert result.narrative_structured.confidence > 0


def test_openai_narrator_fallback_on_missing_key(sample_rca, sample_kpis, monkeypatch):
    from tnic.config import get_settings
    from tnic.services.report_generator import OpenAIRCANarrator

    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-invalid")
    monkeypatch.setattr(settings, "enable_openai_reports", True)

    narrator = OpenAIRCANarrator()
    report = narrator.narrate(sample_rca, kpis=sample_kpis)
    assert report.source == "template"
    assert report.executive_summary


def test_confidence_from_top_finding(sample_rca, sample_kpis):
    from tnic.services.report_generator import narrate_master_rca

    report = narrate_master_rca(sample_rca, kpis=sample_kpis)
    assert report.confidence == pytest.approx(0.82, abs=0.01)
