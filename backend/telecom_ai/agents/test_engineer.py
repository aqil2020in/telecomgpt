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
    from analytics.kaggle_charts import pick_csv_path, build_kaggle_dashboard
    from analytics.link_budget import explain_sinr_vs_rsrq_link_budget, looks_like_link_budget_query
    from analytics.network_kpi import analyze_network_kpi

    path = _upload_csv(session_id) or str(pick_csv_path(query) or "")
    ql = query.lower()
    net_filter = "5g" if "5g" in ql and "4g" not in ql else None

    if looks_like_link_budget_query(query):
        lb = explain_sinr_vs_rsrq_link_budget(query)
        parts = [lb]
        if path:
            result = analyze_network_kpi(path, network_filter=net_filter)
            parts.append("\n\n---\n\n**Measured KPIs from uploaded CSV**\n\n" + result.get("report", ""))
            dash = build_kaggle_dashboard(query, csv_path=path)
            return {
                "agent": "rf_metrics",
                "content": "\n".join(parts) + _readiness_note("rf_metrics"),
                "artifacts": list(dash.get("charts") or []),
                "tool_calls": [{"tool": "explain_link_budget", "ok": True}, {"tool": "analyze_network_kpi", "path": path}],
                "ready": True,
                "data_status": "loaded",
            }
        return {
            "agent": "rf_metrics",
            "content": lb,
            "artifacts": [],
            "tool_calls": [{"tool": "explain_link_budget", "ok": True}],
            "ready": True,
            "data_status": "computed",
        }

    if not path:
        return {
            "agent": "rf_metrics",
            "content": (
                "**RF Metrics Agent** (ready)\n\n"
                "Upload a CSV with SS-RSRP/Signal Strength, throughput, latency, band columns.\n"
                "Supported partial KPIs: RSRP proxy, DL/UL throughput, latency, per-band stats.\n"
                "Full grading: SS-RSRQ, SS-SINR, CQI, BLER, RI when present.\n"
                "RF fundamentals: GET /api/rf/handbook/reference (ShareTechnote RF Handbook).\n\n"
                "Expected schemas: `network_kpi`, `drive_test_rf` — GET /api/datasets/schemas"
            ),
            "artifacts": [],
            "ready": True,
            "data_status": "awaiting_upload",
        }

    result = analyze_network_kpi(path, network_filter=net_filter)
    dash = build_kaggle_dashboard(query, csv_path=path)
    content = result.get("report", "")
    from analytics.rf_handbook import format_rf_handbook_hints

    hints = format_rf_handbook_hints(query)
    if hints:
        content += "\n\n" + hints
    from analytics.nr_power_class import format_power_class_brief

    pc = format_power_class_brief(query)
    if pc:
        content += "\n\n" + pc
    return {
        "agent": "rf_metrics",
        "content": content + _readiness_note("rf_metrics"),
        "artifacts": list(dash.get("charts") or []),
        "tool_calls": [{"tool": "analyze_network_kpi", "path": path}],
        "ready": True,
        "data_status": "loaded",
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

        ql = query.lower()
        capa_in_log = re.search(r"ue\s*capability|uecapability|bandcombination|featureset", text[:200_000], re.I)
        if capa_in_log or any(k in ql for k in ("capability", "capa", "feature set", "band combo", "ue cap")):
            from analytics.log_ue_capability_check import build_ue_capability_report, format_ue_capability_report

            capa = build_ue_capability_report(text, filename=p.name)
            parts.append(format_ue_capability_report(capa))
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
    from analytics.harq_rrc_fault import (
        explain_rrc_harq_fault,
        looks_like_rrc_harq_fault_query,
    )

    catalog_path = _DATA / "fault_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {"symptoms": []}
    ql = query.lower()

    matches = []
    for item in catalog.get("symptoms", []):
        if any(kw in ql for kw in item.get("keywords", [])):
            matches.append(item)
        elif any(kw in ql for kw in ["fail", "error", "drop", "fault", "troubleshoot", "debug"]):
            continue

    if not matches and any(k in ql for k in ("fail", "error", "drop", "fault", "troubleshoot", "rrc", "pdu", "handover", "throughput")):
        for item in catalog.get("symptoms", []):
            if any(kw.split()[0] in ql for kw in item.get("keywords", [])):
                matches.append(item)

    if not matches:
        matches = catalog.get("symptoms", [])[:2]

    tool_calls: list[dict] = []
    parts: list[str] = []

    logs = _upload_logs(session_id)
    log_text = None
    if logs:
        log_text = logs[0].read_text(encoding="utf-8", errors="replace")

    if looks_like_rrc_harq_fault_query(query):
        rrc = next(
            (m for m in json.loads((_DATA / "fault_catalog.json").read_text(encoding="utf-8")).get("symptoms", [])
             if m.get("id") == "rrc_setup_fail"),
            None,
        ) if (_DATA / "fault_catalog.json").exists() else None
        header: list[str] = []
        if rrc:
            header = [
                "**Fault catalog — RRC setup fail** (expanded)",
                "",
                "**Top likely causes:**",
            ]
            for c in (rrc.get("likely_causes") or [])[:4]:
                header.append(f"- {c}")
            header.append("")
        harq_md = explain_rrc_harq_fault(query, log_text=log_text)
        parts.append(("\n".join(header) + "\n\n" + harq_md) if header else harq_md)
        tool_calls.append({"tool": "explain_rrc_harq_fault", "ok": True})
    else:
        lines = ["**Fault Analysis Agent** (catalog ready — improves with your logs/alarms)\n"]
        for m in matches[:3]:
            lines.append(f"### {m.get('id', 'symptom').replace('_', ' ').title()}")
            lines.append("**Likely causes:**")
            for c in m.get("likely_causes", []):
                lines.append(f"- {c}")
            lines.append("**Recommended checks:**")
            for c in m.get("checks", []):
                lines.append(f"- {c}")
            lines.append(f"**Specs:** {', '.join(m.get('spec_refs', []))}")
        parts.append("\n".join(lines))

        rrc_match = next((m for m in matches if m.get("id") == "rrc_setup_fail"), None)
        if rrc_match and rrc_match.get("harq_sections"):
            harq_md = explain_rrc_harq_fault(query, log_text=log_text)
            parts.append("\n\n---\n\n" + harq_md)
            tool_calls.append({"tool": "explain_rrc_harq_fault", "ok": True})

    if logs and not looks_like_rrc_harq_fault_query(query):
        parts.append(f"\n*Session logs available ({len(logs)}) — HARQ/RRC scan included when RRC fault is detected.*")

    from analytics.nr_protocol_stack import format_protocol_stack_brief

    stack = format_protocol_stack_brief(query)
    if stack and not looks_like_rrc_harq_fault_query(query):
        parts.append("\n" + stack)

    return {
        "agent": "fault_analysis",
        "content": "\n\n".join(p for p in parts if p),
        "artifacts": [],
        "tool_calls": tool_calls,
        "ready": True,
        "data_status": "builtin_catalog" if not log_text else "catalog_and_log",
    }


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
        elif "ca" in ql or "n77" in ql or "n78" in ql:
            selected = [t for t in templates if t.get("id") == "ca_n77_n78"]
        elif "vonr" in ql or "voice" in ql:
            selected = [t for t in templates if t.get("id") == "vonr_call"]
        elif "capability" in ql or "capa" in ql or "feature set" in ql or "ue cap" in ql:
            selected = [t for t in templates if t.get("id") == "nr_ue_capability"]
        elif "hpue" in ql or "power class" in ql or "powerclass" in ql:
            selected = [t for t in templates if t.get("id") == "nr_hpue_power_class"]
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
        from analytics.nr_power_class import format_power_class_brief

        idle = (
            "**BTS Config Agent** (ready)\n\n"
            "Upload gNB/BTS export (JSON, XML, or CLI `.txt`) to validate:\n"
            "- Band / numerology / SSB / PRACH parameters\n"
            "- Diff vs golden baseline (when you provide one)\n"
            "- Cross-check against 3GPP limits\n\n"
            "Until then, ask spec questions: e.g. *Validate n78 SSB pattern per 38.104*\n"
            "Power class reference: GET /api/nr/power-class/reference"
        )
        pc = format_power_class_brief(query)
        if pc:
            idle += "\n\n" + pc
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
    from analytics.nr_power_class import format_power_class_brief

    pc = format_power_class_brief(query)
    if pc:
        lines.append("\n" + pc)
    return {
        "agent": "bts_config",
        "content": "\n".join(lines),
        "artifacts": [],
        "ready": True,
        "data_status": "partial",
    }
