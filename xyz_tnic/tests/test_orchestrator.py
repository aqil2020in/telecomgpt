"""Master RCA orchestrator tests."""

from __future__ import annotations

from tnic.models.schemas import AnalyzeRequest, KPIInput
from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator, ORCHESTRATION_MAP


def test_orchestration_map_covers_primary_issues():
    expected = {"handover", "rlf", "call_drop", "throughput", "rach", "beamforming", "latency"}
    assert expected.issubset(set(ORCHESTRATION_MAP.keys()))


def test_call_drop_rca_runs_multiple_agents(degraded_kpis):
    orch = MasterRCAOrchestrator()
    req = AnalyzeRequest(
        query="Root cause analysis call drop cell 43211",
        kpis=KPIInput(**{k: v for k, v in degraded_kpis.items() if k in KPIInput.model_fields}),
    )
    result = orch.run(req)
    assert result.issue_type == "call_drop"
    assert len(result.agents_run) >= 3
    assert "call_drop_agent" in result.agents_run
    assert result.health_score is not None
    assert len(result.probable_root_causes) >= 1
    assert len(result.recommended_actions) >= 1
    assert len(result.validation_checklist) >= 1


def test_throughput_rca(degraded_kpis):
    orch = MasterRCAOrchestrator()
    req = AnalyzeRequest(
        query="low throughput troubleshooting",
        issue_type="throughput",
        kpis=KPIInput(**{k: v for k, v in degraded_kpis.items() if k in KPIInput.model_fields}),
    )
    result = orch.run(req)
    assert result.issue_type == "throughput"
    assert "throughput_agent" in result.agents_run


def test_knowledge_graph_built(degraded_kpis):
    orch = MasterRCAOrchestrator()
    req = AnalyzeRequest(query="handover fail", kpis=KPIInput(ho_success_rate=91.0))
    result = orch.run(req)
    assert result.knowledge_graph is not None
    assert len(result.knowledge_graph.nodes) >= 2
