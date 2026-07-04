"""Test Engineer specialist agents — ready without full datasets; optimize when data provided."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..loaders import TelecomDB
    from ..tools import ToolRegistry

_DATA = Path(__file__).resolve().parent.parent.parent / "data"


def _upload_csv(session_id: str) -> str | None:
    uploads = _DATA / "uploads" / session_id
    if uploads.exists():
        csvs = sorted(uploads.glob("*.csv"))
        if csvs:
            return str(csvs[0])
    return None


def _upload_logs(session_id: str) -> list[Path]:
    uploads = _DATA / "uploads" / session_id
    if not uploads.exists():
        return []
    return sorted(list(uploads.glob("*.log")) + list(uploads.glob("*.txt")))


def _upload_configs(session_id: str) -> list[Path]:
    uploads = _DATA / "uploads" / session_id
    if not uploads.exists():
        return []
    return sorted(list(uploads.glob("*.json")) + list(uploads.glob("*.xml")))


def _readiness_note(agent: str) -> str:
    from analytics.dataset_registry import dataset_readiness

    r = dataset_readiness()
    for a in r.get("agents", []):
        if a.get("agent") == agent and not a.get("ready") and not a.get("builtin"):
            return (
                "\n\n*Agent is ready — upload matching datasets to unlock full analysis. "
                f"See GET /api/datasets/status for schema requirements.*"
            )
    return ""


def run_rf_metrics_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    """Deprecated for 2GB demo — redirect to TNIC RCA or coverage optimizer."""
    from tnic.bridge import run_tnic_rca_markdown

    return {
        "agent": "rf_metrics",
        "content": run_tnic_rca_markdown(query, session_id=session_id),
        "artifacts": [],
        "tool_calls": [{"tool": "tnic_rca", "ok": True}],
        "ready": True,
        "data_status": "tnic_redirect",
    }


def run_log_debug_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    from analytics.log_tools import log_summary

    logs = _upload_logs(session_id)
    if not logs:
        return {
            "agent": "log_debug",
            "content": (
                "**Log Debug Agent** (ready)\n\n"
                "Upload QXDM/QCAT/UE `.log` or `.txt` for:\n"
                "- Error clustering and top faults\n"
                "- RRC/NAS keyword scan\n"
                "- Procedure hints linked to 3GPP\n"
                "- Protocol stack layer scan (PHY→NAS)\n\n"
                "Reference: GET /api/nr/protocol-stack/reference\n\n"
                "Without a log, ask a fault question to use the built-in fault catalog."
            ),
            "artifacts": [],
            "ready": True,
            "data_status": "awaiting_upload",
        }

    parts = []
    artifacts = []
    for p in logs[:2]:
        text = p.read_text(encoding="utf-8", errors="replace")
        s = log_summary(text)
        parts.append(
            f"**Log:** `{p.name}` — {s['total_lines']} lines, {s['error_count']} errors\n"
            f"Levels: {s.get('level_counts')}\n"
            f"Top errors: {s.get('top_errors', [])[:3]}"
        )
        from analytics.log_attach_check import build_attach_report, format_attach_report

        report = build_attach_report(text, filename=p.name)
        parts.append(format_attach_report(report))
        if report.get("alerts"):
            parts.append("**Alerts:** " + "; ".join(report["alerts"]))

        rrc = len(re.findall(r"\b(RRC|NAS|MAC|RLC|PDCP|RACH|PRACH)\b", text[:100_000], re.I))
        parts.append(f"RRC/NAS/L2 keywords (sample): {rrc} hits")

        from analytics.nr_protocol_stack import format_log_stack_scan, format_protocol_stack_brief

        stack_scan = format_log_stack_scan(text)
        if stack_scan:
            parts.append(stack_scan)
        stack_hint = format_protocol_stack_brief(query)
        if stack_hint:
            parts.append(stack_hint)
        if s.get("level_counts"):
            from analytics.charts import level_counts_chart

            artifacts.append({
                "type": "chart", "ok": True, "title": f"Log levels — {p.name}",
                "plotly_json": level_counts_chart(s["level_counts"]).to_json(),
            })

    return {
        "agent": "log_debug",
        "content": "\n\n".join(parts),
        "artifacts": artifacts,
        "ready": True,
        "data_status": "loaded",
    }


def run_fault_analysis_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    from tnic.fault_agent import run_fault_analysis_agent as tnic_fault

    return tnic_fault(query, tools, session_id=session_id)


def run_feature_validation_agent(query: str, db: "TelecomDB", tools: "ToolRegistry") -> dict:
    tpl_path = _DATA / "feature_test_templates.json"
    templates = json.loads(tpl_path.read_text(encoding="utf-8")).get("templates", []) if tpl_path.exists() else []
    ql = query.lower()

    selected = []
    for t in templates:
        if t.get("feature", "").lower() in ql or t.get("id", "").replace("_", " ") in ql:
            selected.append(t)
    if not selected:
        if "sa" in ql or "registration" in ql:
            selected = [t for t in templates if t.get("id") == "nr_sa_registration"]
        elif "nsa" in ql or "endc" in ql:
            selected = [t for t in templates if t.get("id") == "nr_nsa_endc"]
        elif "vonr" in ql or "voice" in ql:
            selected = [t for t in templates if t.get("id") == "vonr_call"]
        elif "protocol stack" in ql or "stack architecture" in ql or "c-plane" in ql or "u-plane" in ql:
            selected = [t for t in templates if t.get("id") == "nr_protocol_stack"]

    if not selected:
        selected = templates[:2]

    lines = ["**Feature Validation Agent** (built-in test templates — customize with your plans)\n"]
    for t in selected:
        lines.append(f"### {t.get('feature')} ({t.get('3gpp_ref')})")
        lines.append("**Preconditions:** " + "; ".join(t.get("preconditions", [])))
        lines.append("**Steps:**")
        for i, step in enumerate(t.get("steps", []), 1):
            lines.append(f"{i}. {step}")
        lines.append("**Pass criteria:**")
        for p in t.get("pass_criteria", []):
            lines.append(f"- {p}")

    lines.append("\n*Upload a feature test CSV/JSON to replace templates with your lab plans.*")
    return {
        "agent": "feature_validation",
        "content": "\n".join(lines),
        "artifacts": [],
        "ready": True,
        "data_status": "builtin_templates",
    }


def run_bts_config_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    configs = _upload_configs(session_id)
    if not configs:
        idle = (
            "**BTS Config Agent** (ready)\n\n"
            "Upload gNB/BTS export (JSON, XML, or CLI `.txt`) to validate:\n"
            "- Band / numerology / SSB / PRACH parameters\n"
            "- Diff vs golden baseline (when you provide one)\n"
            "- Cross-check against 3GPP limits\n\n"
            "Until then, ask spec questions: e.g. *Validate n78 SSB pattern per 38.104*"
        )
        return {
            "agent": "bts_config",
            "content": idle,
            "artifacts": [],
            "ready": True,
            "data_status": "awaiting_upload",
        }

    lines = ["**BTS Config Agent** — file inspection (full parser when you provide vendor format)\n"]
    for p in configs[:2]:
        text = p.read_text(encoding="utf-8", errors="replace")[:8000]
        lines.append(f"**File:** `{p.name}` ({len(text)} chars sampled)")
        params = re.findall(
            r"(?i)(n\d{1,3}|ssb|prach|numerology|arfcn|pci|tdd|bandwidth|power|qrxlevmin|qqualmin)[^\n]{0,80}",
            text,
        )
        if params:
            lines.append("**Parameters detected (keyword scan):**")
            for hit in params[:12]:
                lines.append(f"- `{hit.strip()}`")
        else:
            lines.append("- No NR keywords matched — provide vendor-specific template for deeper parse.")

    lines.append("\n*Next: upload golden config for diff; vendor schema improves accuracy.*")
    return {
        "agent": "bts_config",
        "content": "\n".join(lines),
        "artifacts": [],
        "ready": True,
        "data_status": "partial",
    }
