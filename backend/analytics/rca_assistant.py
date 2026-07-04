"""AI-powered RCA assistant for 5G network issues — symptom → rules → probable cause → actions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_WORKFLOWS_PATH = Path(__file__).resolve().parent.parent / "data" / "rca_workflows.json"

_RCA_KW = (
    "rca",
    "root cause",
    "root-cause",
    "probable cause",
    "failure analysis",
    "troubleshoot",
    "troubleshooting",
    "fault analysis",
)

_ISSUE_KW = (
    "call drop",
    "dropped call",
    "low throughput",
    "throughput degradation",
    "high latency",
    "rach fail",
    "rach failure",
    "prach fail",
    "handover fail",
    "ho fail",
    "rlf",
    "qdrop",
)

_KPI_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cqi", re.compile(r"\bcqi\s*[=:]\s*(\d+(?:\.\d+)?)", re.I)),
    ("cqi", re.compile(r"\bcqi\s+(?:is\s+)?(\d+(?:\.\d+)?)", re.I)),
    ("bler", re.compile(r"\bbler\s*[=:]\s*(\d+(?:\.\d+)?)\s*%?", re.I)),
    ("bler", re.compile(r"\b(?:dl\s+)?bler\s+(?:is\s+)?(\d+(?:\.\d+)?)\s*%?", re.I)),
    ("ss_rsrp", re.compile(r"\b(?:ss-)?rsrp\s*[=:]\s*(-?\d+(?:\.\d+)?)", re.I)),
    ("ss_rsrq", re.compile(r"\b(?:ss-)?rsrq\s*[=:]\s*(-?\d+(?:\.\d+)?)", re.I)),
    ("ss_sinr", re.compile(r"\b(?:ss-)?sinr\s*[=:]\s*(-?\d+(?:\.\d+)?)", re.I)),
    ("ri", re.compile(r"\b(?:ri|rank)\s*[=:]\s*(\d+(?:\.\d+)?)", re.I)),
    ("ri", re.compile(r"\bstuck\s+(?:at\s+)?rank[- ]?(\d+)", re.I)),
]


def load_rca_workflows() -> dict[str, Any]:
    if not _WORKFLOWS_PATH.exists():
        return {"workflows": []}
    return json.loads(_WORKFLOWS_PATH.read_text(encoding="utf-8"))


def looks_like_rca_query(query: str) -> bool:
    """True when query requests RCA-style network troubleshooting."""
    ql = query.lower().strip()
    if not ql:
        return False

    from analytics.harq_rrc_fault import looks_like_rrc_harq_fault_query
    from analytics.link_budget import looks_like_link_budget_query
    from analytics.coverage_optimizer import looks_like_coverage_optimizer_query

    if looks_like_rrc_harq_fault_query(query):
        return False
    if looks_like_link_budget_query(query) or looks_like_coverage_optimizer_query(query):
        return False

    if any(k in ql for k in _RCA_KW):
        return True
    if any(k in ql for k in _ISSUE_KW):
        return True
    if "fault" in ql and any(k in ql for k in ("drop", "throughput", "rach", "handover", "latency", "ho")):
        return True
    return False


def match_workflows(query: str) -> list[dict[str, Any]]:
    """Return workflows ranked by keyword relevance."""
    ql = query.lower()
    workflows = load_rca_workflows().get("workflows") or []
    scored: list[tuple[int, dict[str, Any]]] = []

    for wf in workflows:
        score = 0
        for kw in wf.get("keywords") or []:
            if kw in ql:
                score += 3
            elif kw.split()[0] in ql:
                score += 1
        if score:
            scored.append((score, wf))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [wf for _, wf in scored]


def parse_inline_kpis(query: str) -> dict[str, float]:
    """Extract KPI values embedded in natural-language query."""
    values: dict[str, float] = {}
    for kpi_id, pat in _KPI_PATTERNS:
        m = pat.search(query)
        if m:
            try:
                values[kpi_id] = float(m.group(1))
            except ValueError:
                continue
    return values


def _rule_matches(when: dict[str, dict[str, float]], kpi_values: dict[str, float]) -> bool:
    for kpi_id, bounds in when.items():
        val = kpi_values.get(kpi_id)
        if val is None:
            return False
        if "min" in bounds and val < bounds["min"]:
            return False
        if "max" in bounds and val > bounds["max"]:
            return False
    return True


def _kpi_values_from_csv(csv_path: str) -> dict[str, float]:
    from analytics.rf_kpi import evaluate_rf_kpis

    result = evaluate_rf_kpis(csv_path)
    values: dict[str, float] = {}
    for kpi_id, m in (result.get("metrics") or {}).items():
        if m.get("present") and m.get("mean") is not None:
            values[kpi_id] = float(m["mean"])
    return values


def _merge_kpi_values(*sources: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for src in sources:
        merged.update(src)
    return merged


def apply_rules(
    workflow: dict[str, Any],
    kpi_values: dict[str, float],
) -> list[dict[str, Any]]:
    """Evaluate workflow rules against KPI values; return matched diagnoses."""
    hits: list[dict[str, Any]] = []
    for rule in workflow.get("rules") or []:
        when = rule.get("when") or {}
        if not when or not _rule_matches(when, kpi_values):
            continue
        hits.append({
            "rule_id": rule.get("id"),
            "probable_cause": rule.get("probable_cause"),
            "confidence": float(rule.get("confidence") or 0.65),
            "actions": rule.get("actions") or [],
            "evidence": {k: kpi_values[k] for k in when if k in kpi_values},
        })
    hits.sort(key=lambda x: x["confidence"], reverse=True)
    return hits


def scan_log_for_rca(log_text: str, workflow: dict[str, Any], *, max_bytes: int = 400_000) -> dict[str, Any]:
    text = log_text[:max_bytes]
    lower = text.lower()
    patterns = workflow.get("log_patterns") or []
    hits = [p for p in patterns if p.lower() in lower]

    sample_lines: list[str] = []
    for line in text.splitlines():
        ll = line.lower()
        if any(p in ll for p in patterns):
            sample_lines.append(line.strip()[:200])
        if len(sample_lines) >= 8:
            break

    return {
        "pattern_hits": hits,
        "sample_lines": sample_lines,
        "line_count": len(text.splitlines()),
    }


def _resolve_csv_path(session_id: str, csv_path: str | None) -> str:
    if csv_path:
        return csv_path
    uploads = Path(__file__).resolve().parent.parent / "data" / "uploads" / (session_id or "default")
    if uploads.exists():
        csvs = sorted(uploads.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if csvs:
            return str(csvs[0])
    return ""


def _resolve_log_text(session_id: str, log_text: str | None) -> str | None:
    if log_text:
        return log_text
    uploads = Path(__file__).resolve().parent.parent / "data" / "uploads" / (session_id or "default")
    if uploads.exists():
        logs = sorted(
            list(uploads.glob("*.log")) + list(uploads.glob("*.txt")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if logs:
            return logs[0].read_text(encoding="utf-8", errors="replace")
    return None


def run_rca_assistant(
    query: str = "",
    *,
    session_id: str = "default",
    csv_path: str | None = None,
    log_text: str | None = None,
) -> dict[str, Any]:
    """Run RCA workflow matching, KPI rules, optional CSV/log enrichment."""
    workflows = match_workflows(query)
    if not workflows and looks_like_rca_query(query):
        workflows = (load_rca_workflows().get("workflows") or [])[:1]

    workflow = workflows[0] if workflows else None
    if not workflow:
        return {"ok": False, "error": "No matching RCA workflow", "query": query}

    inline_kpis = parse_inline_kpis(query)
    path = _resolve_csv_path(session_id, csv_path)
    csv_kpis = _kpi_values_from_csv(path) if path else {}
    kpi_values = _merge_kpi_values(csv_kpis, inline_kpis)

    rule_hits = apply_rules(workflow, kpi_values) if kpi_values else []

    log = _resolve_log_text(session_id, log_text)
    log_scan = scan_log_for_rca(log, workflow) if log else None

    kpi_report = None
    if path:
        from analytics.rf_kpi import evaluate_rf_kpis, format_kpi_report

        kpi_report = evaluate_rf_kpis(path)

    probable_causes: list[dict[str, Any]] = []
    for hit in rule_hits[:3]:
        conf = hit["confidence"]
        if log_scan and log_scan.get("pattern_hits"):
            conf = min(0.95, conf + 0.08)
        probable_causes.append({
            "cause": hit["probable_cause"],
            "confidence": round(conf, 2),
            "evidence": hit.get("evidence") or {},
            "source": "rule",
        })

    if not probable_causes:
        for i, cause in enumerate((workflow.get("likely_causes") or [])[:3]):
            conf = 0.55 - i * 0.05
            if log_scan and log_scan.get("pattern_hits"):
                conf = min(0.85, conf + 0.12)
            probable_causes.append({
                "cause": cause,
                "confidence": round(max(conf, 0.35), 2),
                "evidence": {},
                "source": "catalog",
            })

    actions: list[str] = []
    for hit in rule_hits[:2]:
        actions.extend(hit.get("actions") or [])
    if not actions:
        actions = list(workflow.get("actions") or [])[:4]

    return {
        "ok": True,
        "query": query,
        "issue_id": workflow.get("id"),
        "title": workflow.get("title"),
        "symptoms": workflow.get("symptoms") or [],
        "probable_causes": probable_causes,
        "related_kpis": kpi_values,
        "kpi_csv_path": path or None,
        "kpi_report": kpi_report,
        "recommended_actions": actions[:6],
        "validation_checklist": workflow.get("validation_checklist") or [],
        "checks": workflow.get("checks") or [],
        "spec_refs": workflow.get("spec_refs") or [],
        "log_scan": log_scan,
        "workflows_matched": [w.get("id") for w in workflows[:3]],
    }


def format_rca_report(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return f"**RCA Assistant** — {result.get('error', 'No result')}"

    lines = [
        f"## RCA Assistant — {result.get('title', 'Network issue')}",
        "",
        "Structured root-cause analysis: symptom → KPI/rules → probable cause → actions.",
        "",
        f"**Issue type:** `{result.get('issue_id')}`",
    ]

    if result.get("symptoms"):
        lines.append("\n**Observed symptoms (typical):**")
        for s in result["symptoms"]:
            lines.append(f"- {s}")

    if result.get("probable_causes"):
        lines.append("\n**Probable root causes:**")
        for pc in result["probable_causes"]:
            conf = int(float(pc.get("confidence", 0)) * 100)
            lines.append(f"- **{pc['cause']}** — confidence ~{conf}%")
            if pc.get("evidence"):
                ev = ", ".join(f"{k}={v}" for k, v in pc["evidence"].items())
                lines.append(f"  - Evidence: {ev}")

    if result.get("related_kpis"):
        lines.append("\n**Related KPIs:**")
        for k, v in result["related_kpis"].items():
            lines.append(f"- {k}: **{v}**")

    if result.get("kpi_report"):
        from analytics.rf_kpi import format_kpi_report

        lines.append("\n" + format_kpi_report(result["kpi_report"]))

    if result.get("recommended_actions"):
        lines.append("\n**Recommended actions:**")
        seen: set[str] = set()
        for a in result["recommended_actions"]:
            if a not in seen:
                lines.append(f"- {a}")
                seen.add(a)

    if result.get("checks"):
        lines.append("\n**Diagnostic checks:**")
        for c in result["checks"][:6]:
            lines.append(f"- {c}")

    if result.get("validation_checklist"):
        lines.append("\n**Validation checklist:**")
        for v in result["validation_checklist"]:
            lines.append(f"- [ ] {v}")

    if result.get("log_scan") and result["log_scan"].get("pattern_hits"):
        scan = result["log_scan"]
        lines.append("\n**Log scan hints:**")
        lines.append(f"- Patterns: {', '.join(scan['pattern_hits'])}")
        for ln in (scan.get("sample_lines") or [])[:4]:
            lines.append(f"- `{ln}`")

    if result.get("spec_refs"):
        lines.append(f"\n**3GPP refs:** {', '.join(result['spec_refs'])}")

    return "\n".join(lines)


def explain_rca_assistant(
    query: str = "",
    *,
    session_id: str = "default",
    csv_path: str | None = None,
    log_text: str | None = None,
) -> str:
    return format_rca_report(run_rca_assistant(query, session_id=session_id, csv_path=csv_path, log_text=log_text))


def rca_assistant_dict(
    query: str = "",
    *,
    session_id: str = "default",
    csv_path: str | None = None,
    log_text: str | None = None,
) -> dict[str, Any]:
    result = run_rca_assistant(query, session_id=session_id, csv_path=csv_path, log_text=log_text)
    result["markdown"] = format_rca_report(result)
    return result
