"""Rewrite fault_analysis to use TNIC RCA engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telecom_ai.tools import ToolRegistry

_DATA = Path(__file__).resolve().parent.parent / "data"


def _upload_logs(session_id: str) -> list[Path]:
    uploads = _DATA / "uploads" / (session_id or "default")
    if not uploads.exists():
        return []
    return sorted(
        list(uploads.glob("*.log")) + list(uploads.glob("*.txt")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def run_fault_analysis_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    from analytics.harq_rrc_fault import explain_rrc_harq_fault, looks_like_rrc_harq_fault_query
    from tnic.bridge import looks_like_tnic_rca_query, run_tnic_rca_markdown

    tool_calls: list[dict] = []
    logs = _upload_logs(session_id)
    log_text = logs[0].read_text(encoding="utf-8", errors="replace") if logs else None

    # RRC/HARQ deep-dive (specialized)
    if looks_like_rrc_harq_fault_query(query):
        catalog_path = _DATA / "fault_catalog.json"
        rrc = None
        if catalog_path.exists():
            rrc = next(
                (m for m in json.loads(catalog_path.read_text(encoding="utf-8")).get("symptoms", [])
                 if m.get("id") == "rrc_setup_fail"),
                None,
            )
        header: list[str] = []
        if rrc:
            header = ["**Fault catalog — RRC setup fail**", ""]
            for c in (rrc.get("likely_causes") or [])[:4]:
                header.append(f"- {c}")
            header.append("")
        harq_md = explain_rrc_harq_fault(query, log_text=log_text)
        content = ("\n".join(header) + "\n\n" + harq_md) if header else harq_md
        tool_calls.append({"tool": "explain_rrc_harq_fault", "ok": True})
        return {
            "agent": "fault_analysis",
            "content": content,
            "artifacts": [],
            "tool_calls": tool_calls,
            "ready": True,
            "data_status": "catalog_and_log" if log_text else "builtin_catalog",
        }

    # TNIC multi-agent RCA (HO, RLF, call drop, throughput, RACH, beam, latency)
    md = run_tnic_rca_markdown(query, session_id=session_id, log_text=log_text, generate_report=False)
    tool_calls.append({"tool": "tnic_rca", "ok": True})
    return {
        "agent": "fault_analysis",
        "content": md,
        "artifacts": [],
        "tool_calls": tool_calls,
        "ready": True,
        "data_status": "tnic_rca" if log_text else "tnic_rules",
    }
