"""RCA orchestrator tests."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["APP_ENV"] = "test"

from app.models.schemas import AnalyzeRequest, KPIInput
from app.orchestrator.rca_orchestrator import MasterRCAOrchestrator


def test_orchestrator_throughput():
    orch = MasterRCAOrchestrator()
    req = AnalyzeRequest(
        query="RCA low throughput cell 43211",
        issue_type="throughput",
        kpis=KPIInput(cqi=7.3, bler=15.2, throughput_mbps=28.5, ri=1.1, ss_sinr=4.2),
        include_rag=False,
        generate_report=False,
    )
    result = orch.run(req)
    assert result.ok
    assert result.issue_type == "throughput"
    assert len(result.findings) >= 1
    assert result.health_score is not None
    assert result.knowledge_graph is not None


def test_orchestrator_handover():
    orch = MasterRCAOrchestrator()
    req = AnalyzeRequest(
        query="HO preparation failure",
        kpis=KPIInput(ho_prep_fail_rate=7.0, ho_success_rate=91.0),
        include_rag=False,
    )
    result = orch.run(req)
    assert any("handover" in f.category or "ho" in f.rule_id for f in result.findings)


if __name__ == "__main__":
    test_orchestrator_throughput()
    test_orchestrator_handover()
    print("Orchestrator tests passed.")
