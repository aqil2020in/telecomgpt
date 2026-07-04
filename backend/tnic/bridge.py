"""Bridge TNIC RCA engine into TelecomGPT fault_analysis and fast-kb paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parent.parent / "data"


def _resolve_log_text(session_id: str, log_text: str | None) -> str | None:
    if log_text:
        return log_text
    uploads = _DATA / "uploads" / (session_id or "default")
    if uploads.exists():
        logs = sorted(
            list(uploads.glob("*.log")) + list(uploads.glob("*.txt")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if logs:
            return logs[0].read_text(encoding="utf-8", errors="replace")
    return None


def _kpis_from_session_csv(session_id: str) -> dict[str, Any]:
    uploads = _DATA / "uploads" / (session_id or "default")
    if not uploads.exists():
        return {}
    csvs = sorted(uploads.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csvs:
        return {}
    try:
        from tnic.services.pm_ingestion import aggregate_cell_kpis

        agg = aggregate_cell_kpis(csvs[0])
        if agg:
            return next(iter(agg.values()), {})
    except Exception:
        pass
    return {}


def looks_like_tnic_rca_query(query: str) -> bool:
    from analytics.harq_rrc_fault import looks_like_rrc_harq_fault_query

    if looks_like_rrc_harq_fault_query(query):
        return False

    ql = query.lower()
    keys = (
        "rca", "root cause", "troubleshoot", "fault analysis", "call drop",
        "handover fail", "ho fail", "low throughput", "rach fail", "prach fail",
        "rlf", "latency spike", "beam failure", "network intelligence",
    )
    return any(k in ql for k in keys)


def run_tnic_rca_markdown(
    query: str,
    *,
    session_id: str = "default",
    log_text: str | None = None,
    generate_report: bool = False,
) -> str:
    from tnic.models.schemas import AnalyzeRequest, KPIInput
    from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator
    from tnic.rag.retriever import get_rag_store

    csv_kpis = _kpis_from_session_csv(session_id)
    kpi_input = KPIInput(**{k: v for k, v in csv_kpis.items() if k in KPIInput.model_fields})

    rag = get_rag_store().search(query, k=3)
    orch = MasterRCAOrchestrator()
    result = orch.run(
        AnalyzeRequest(
            query=query,
            kpis=kpi_input,
            include_rag=True,
            generate_report=generate_report,
        ),
        rag_context=rag,
    )

    from tnic.orchestrator.rca_orchestrator import _validation_checklist
    from tnic.services.health_scoring import compute_health_score

    lines = [
        "## XYZ Network Intelligence — RCA Report",
        "",
        f"**Issue domain:** `{result.issue_type}`",
        f"**Health score:** {result.health_score}/100" if result.health_score else "",
        "",
    ]

    if result.probable_root_causes:
        lines.append("**Probable root causes:**")
        for pc in result.probable_root_causes[:4]:
            conf = int(float(pc.get("confidence", 0)) * 100)
            lines.append(f"- **{pc['cause']}** (~{conf}%)")

    if result.recommended_actions:
        lines.append("\n**Recommended actions:**")
        for a in result.recommended_actions[:6]:
            lines.append(f"- {a}")

    if result.validation_checklist:
        lines.append("\n**Validation checklist:**")
        for v in result.validation_checklist[:5]:
            lines.append(f"- [ ] {v}")

    log = _resolve_log_text(session_id, log_text)
    if log and result.findings:
        lines.append(f"\n*Log attached ({len(log.splitlines())} lines) — agents: {', '.join(result.agents_run)}*")

    if result.narrative_report:
        lines.append("\n---\n\n" + result.narrative_report)

    return "\n".join(l for l in lines if l is not None)


def run_tnic_rca_dict(
    query: str,
    *,
    session_id: str = "default",
    generate_report: bool = False,
) -> dict[str, Any]:
    from tnic.models.schemas import AnalyzeRequest, KPIInput
    from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator
    from tnic.rag.retriever import get_rag_store

    csv_kpis = _kpis_from_session_csv(session_id)
    kpi_input = KPIInput(**{k: v for k, v in csv_kpis.items() if k in KPIInput.model_fields})
    rag = get_rag_store().search(query, k=3)
    result = orch.run(
        AnalyzeRequest(query=query, kpis=kpi_input, include_rag=True, generate_report=generate_report),
        rag_context=rag,
    ) if (orch := MasterRCAOrchestrator()) else None
    return result.model_dump() if result else {"ok": False}
