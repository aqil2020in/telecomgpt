"""NR UE Capability log checker — ShareTechnote / TS 38.306 procedure hints."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REF = Path(__file__).resolve().parent.parent / "data" / "nr_ue_capability_reference.json"
_BAND_RE = re.compile(r"\bn(28|41|48|66|71|77|78|79|258|260|261)\b", re.I)


def load_ue_capability_reference() -> dict[str, Any]:
    if not _REF.exists():
        return {}
    return json.loads(_REF.read_text(encoding="utf-8"))


def _match_any(text: str, lower: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        if pat.lower() in lower:
            return pat
        try:
            if re.search(pat, text, re.I):
                return pat
        except re.error:
            continue
    return None


def _extract_bands(text: str, *, limit: int = 20) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _BAND_RE.finditer(text):
        b = m.group(0).lower()
        if b not in seen:
            seen.add(b)
            out.append(b)
        if len(out) >= limit:
            break
    return out


def check_ue_capability_log(log_text: str, *, max_bytes: int = 800_000) -> dict[str, Any]:
    """Scan log for UE Capability Enquiry/Information and key IE hints."""
    text = log_text[:max_bytes]
    lower = text.lower()
    ref = load_ue_capability_reference()

    steps_out: list[dict[str, Any]] = []
    required_passed = 0
    required_total = 0

    for step in ref.get("procedure_steps", []):
        matched = _match_any(text, lower, step.get("log_patterns", []))
        optional = step.get("optional", False)
        if not optional:
            required_total += 1
        found = matched is not None
        if found and not optional:
            required_passed += 1
        steps_out.append({
            "id": step.get("id"),
            "label": step.get("label"),
            "direction": step.get("direction"),
            "status": "found" if found else ("optional" if optional else "missing"),
            "matched": matched,
            "note": step.get("note"),
            "optional": optional,
        })

    fields_out: list[dict[str, Any]] = []
    for item in ref.get("field_log_patterns", []):
        matched = _match_any(text, lower, item.get("patterns", []))
        fields_out.append({
            "field": item.get("field"),
            "status": "found" if matched else "not_seen",
            "matched": matched,
        })

    bands = _extract_bands(text)
    segmentation = any(s.get("id") == "segmentation" and s.get("status") == "found" for s in steps_out)

    alerts: list[str] = []
    if steps_out and steps_out[0].get("status") == "missing":
        alerts.append("No UE Capability Enquiry detected — capa exchange may not have started.")
    if len(steps_out) > 1 and steps_out[1].get("status") == "missing":
        alerts.append("No UE Capability Information — check enquiry, SRB, or segmentation reassembly.")
    if segmentation:
        alerts.append("RRC segmentation detected — verify all segments received (9000 byte PDCP SDU limit).")
    if not bands:
        alerts.append("No NR band tokens (n77, n78, …) found in log sample — capa may be encoded/ truncated.")

    for pitfall_kw, msg in [
        ("capability mismatch", "Possible UE capability mismatch reported in log."),
        ("not supported", "Feature 'not supported' string found — cross-check UECapabilityInformation."),
    ]:
        if pitfall_kw in lower:
            alerts.append(msg)

    if required_passed == required_total and required_total > 0:
        overall = "COMPLETE"
    elif required_passed > 0:
        overall = "PARTIAL"
    elif any(f.get("status") == "found" for f in fields_out):
        overall = "FIELDS_ONLY"
    else:
        overall = "NOT_DETECTED"

    first_missing = next(
        (s for s in steps_out if s.get("status") == "missing" and not s.get("optional")),
        None,
    )

    return {
        "ok": True,
        "overall": overall,
        "procedure_passed": required_passed,
        "procedure_total": required_total,
        "steps": steps_out,
        "fields": fields_out,
        "bands_detected": bands,
        "segmentation": segmentation,
        "first_missing": first_missing,
        "alerts": alerts,
        "pitfalls": ref.get("pitfalls", [])[:3],
        "troubleshooting": ref.get("troubleshooting", []),
        "references": [ref.get("reference")] if ref.get("reference") else [],
        "spec_refs": ref.get("spec_refs", []),
    }


def format_ue_capability_report(result: dict[str, Any]) -> str:
    lines = [
        f"**NR UE Capability report** — **{result.get('overall')}** "
        f"({result.get('procedure_passed')}/{result.get('procedure_total')} procedure steps)",
        "",
        "| Step | Direction | Status |",
        "|------|-----------|--------|",
    ]
    for s in result.get("steps", []):
        icon = "✓" if s.get("status") == "found" else ("~" if s.get("status") == "optional" else "✗")
        lines.append(f"| {s.get('label')} | {s.get('direction', '—')} | {icon} |")

    fields_found = [f.get("field") for f in result.get("fields", []) if f.get("status") == "found"]
    if fields_found:
        lines.append("")
        lines.append(f"**IE hints in log:** {', '.join(fields_found)}")

    bands = result.get("bands_detected") or []
    if bands:
        lines.append(f"**Bands mentioned:** {', '.join(bands)}")

    fm = result.get("first_missing")
    if fm and result.get("overall") not in ("COMPLETE",):
        lines.append("")
        lines.append(f"**First gap:** {fm.get('label')} — {fm.get('note', '')}")

    for alert in result.get("alerts", [])[:4]:
        lines.append(f"- ⚠ {alert}")

    return "\n".join(lines)


def build_ue_capability_report(log_text: str, *, filename: str = "log") -> dict[str, Any]:
    result = check_ue_capability_log(log_text)
    result["filename"] = filename
    result["report_md"] = format_ue_capability_report(result)
    return result


def analyze_ue_capability_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return build_ue_capability_report(text, filename=path.name)
