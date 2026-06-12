"""NR SA Initial Attach log checker — ShareTechnote + Amarisoft message sequence."""

from __future__ import annotations

import json
import re
from pathlib import Path

_CHECKLIST = Path(__file__).resolve().parent.parent / "data" / "nr_sa_attach_checklist.json"


def load_attach_checklist() -> dict:
    if not _CHECKLIST.exists():
        return {"steps": []}
    return json.loads(_CHECKLIST.read_text(encoding="utf-8"))


def check_attach_sequence(log_text: str, *, max_bytes: int = 500_000) -> dict:
    """Scan log text for expected NR SA attach messages (best-effort pattern match)."""
    text = log_text[:max_bytes]
    lower = text.lower()
    checklist = load_attach_checklist()
    steps_out: list[dict] = []
    passed = 0

    for step in checklist.get("steps", []):
        found = False
        matched_pattern = None
        for pat in step.get("log_patterns", []):
            if pat.lower() in lower:
                found = True
                matched_pattern = pat
                break
            try:
                if re.search(pat, text, re.I):
                    found = True
                    matched_pattern = pat
                    break
            except re.error:
                continue
        if found:
            passed += 1
        steps_out.append({
            "id": step.get("id"),
            "phase": step.get("phase"),
            "label": step.get("label"),
            "status": "found" if found else "missing",
            "matched": matched_pattern,
            "fail_hint": step.get("fail_hint"),
        })

    total = len(steps_out)
    if passed == total:
        overall = "COMPLETE"
    elif passed >= total * 0.6:
        overall = "PARTIAL"
    elif passed > 0:
        overall = "IN_PROGRESS"
    else:
        overall = "NOT_DETECTED"

    first_missing = next((s for s in steps_out if s["status"] == "missing"), None)

    return {
        "ok": True,
        "overall": overall,
        "passed": passed,
        "total": total,
        "steps": steps_out,
        "first_missing": first_missing,
        "references": checklist.get("references", []),
    }


def format_attach_report(result: dict) -> str:
    lines = [
        f"**NR SA Initial Attach checklist** — **{result.get('overall')}** ({result.get('passed')}/{result.get('total')} steps)",
        "",
        "| Phase | Step | Status |",
        "|-------|------|--------|",
    ]
    for s in result.get("steps", []):
        icon = "✓" if s.get("status") == "found" else "✗"
        lines.append(f"| {s.get('phase')} | {s.get('label')} | {icon} |")
    fm = result.get("first_missing")
    if fm and result.get("overall") != "COMPLETE":
        lines.append("")
        lines.append(f"**First gap:** {fm.get('label')} — {fm.get('fail_hint')}")
    refs = result.get("references") or []
    if refs:
        lines.append("")
        lines.append("References: " + ", ".join(refs))
    return "\n".join(lines)


def build_attach_report(log_text: str, *, filename: str = "log") -> dict:
    """Full attach report: sequence checklist + log error summary."""
    from analytics.log_tools import log_summary

    attach = check_attach_sequence(log_text)
    summary = log_summary(log_text)
    lower = log_text.lower()

    alerts: list[str] = []
    if "authentication failure" in lower or "auth failure" in lower:
        alerts.append("Authentication failure detected — check USIM K / ue_db.cfg (Amarisoft).")
    if "registration reject" in lower:
        alerts.append("Registration reject — check PLMN, subscription, and reject cause.")
    if "rrc reject" in lower or "rrcreject" in lower:
        alerts.append("RRC reject — check cell barring, access class, or RF conditions.")
    if summary.get("error_count", 0) > 0:
        alerts.append(f"Log contains {summary['error_count']} ERROR/FATAL lines.")

    attach["filename"] = filename
    attach["log_summary"] = {
        "total_lines": summary.get("total_lines"),
        "error_count": summary.get("error_count"),
        "level_counts": summary.get("level_counts"),
        "top_errors": summary.get("top_errors", [])[:5],
    }
    attach["alerts"] = alerts
    attach["report_md"] = format_attach_report(attach)
    return attach


def analyze_log_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    return build_attach_report(text, filename=path.name)
