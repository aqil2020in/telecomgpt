"""HARQ / MAC / PHY fault analysis for NR RRC setup failure (K1, RV, HARQ processors, frame structure)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REF_PATH = Path(__file__).resolve().parent.parent / "data" / "harq_rrc_fault_reference.json"

_RRC_FAULT_KW = (
    "rrc fail",
    "rrc failure",
    "rrc setup fail",
    "rrc setup failure",
    "rrcconnectionreject",
    "rrc setup reject",
    "rrc reject",
    "fault analysis rrc",
)
_HARQ_KW = ("harq", "k1", "redundancy", "rv_idx", "msg4", "contention")


def load_harq_rrc_fault_reference() -> dict[str, Any]:
    if not _REF_PATH.exists():
        return {}
    return json.loads(_REF_PATH.read_text(encoding="utf-8"))


def looks_like_rrc_harq_fault_query(query: str) -> bool:
    ql = query.lower().strip()
    if not ql:
        return False
    if any(k in ql for k in _RRC_FAULT_KW):
        return True
    if "rrc" in ql and any(k in ql for k in ("fail", "fault", "troubleshoot", "reject", "error")):
        return True
    if "fault" in ql and "rrc" in ql:
        return True
    return False


def scan_log_for_harq_rrc_faults(log_text: str, *, max_bytes: int = 400_000) -> dict[str, Any]:
    """Best-effort HARQ/RRC fault pattern scan on UE/QXDM text logs."""
    text = log_text[:max_bytes]
    lower = text.lower()
    ref = load_harq_rrc_fault_reference()
    patterns = ref.get("log_scan_patterns") or {}

    hits: dict[str, list[str]] = {}
    for category, pats in patterns.items():
        found = []
        for pat in pats:
            if pat.lower() in lower:
                found.append(pat)
            elif re.search(re.escape(pat), text, re.I):
                found.append(pat)
        if found:
            hits[category] = found[:8]

    # Extract sample lines with HARQ/K1/RV
    sample_lines: list[str] = []
    for line in text.splitlines():
        ll = line.lower()
        if any(k in ll for k in ("harq", "k1=", "rv_idx", "rrc setup", "contention", "prach", "crc=")):
            sample_lines.append(line.strip()[:200])
        if len(sample_lines) >= 12:
            break

    alerts: list[str] = []
    if hits.get("ack_fail"):
        alerts.append("HARQ/CRC/contention failure patterns detected — check Msg4 ACK and RRC Setup retx.")
    if hits.get("k1") and hits.get("ack_fail"):
        alerts.append("K1/HARQ timing present with failure patterns — verify dl-DataToUL-ACK vs DCI K1 index.")
    if hits.get("rv") and hits.get("ack_fail"):
        alerts.append("RV retransmission activity with failures — inspect soft-combining / RF on setup PDSCH.")

    return {
        "ok": True,
        "pattern_hits": hits,
        "sample_lines": sample_lines,
        "alerts": alerts,
        "line_count": len(text.splitlines()),
    }


def format_log_harq_scan(scan: dict[str, Any]) -> str:
    if not scan.get("pattern_hits") and not scan.get("sample_lines"):
        return ""
    lines = ["**Log scan — HARQ / RRC setup hints**"]
    for cat, pats in (scan.get("pattern_hits") or {}).items():
        lines.append(f"- {cat}: {', '.join(pats)}")
    if scan.get("alerts"):
        lines.append("\n**Alerts:**")
        for a in scan["alerts"]:
            lines.append(f"- {a}")
    if scan.get("sample_lines"):
        lines.append("\n**Sample log lines:**")
        for ln in scan["sample_lines"][:8]:
            lines.append(f"- `{ln}`")
    return "\n".join(lines)


def explain_rrc_harq_fault(query: str = "", *, log_text: str | None = None) -> str:
    """Full markdown: K1, RV, HARQ processors, hybrid HARQ, frame structure, examples."""
    ref = load_harq_rrc_fault_reference()
    k1 = ref.get("k1_configuration") or {}
    rv = ref.get("redundancy_version") or {}
    hp = ref.get("harq_processor") or {}
    fs = ref.get("frame_structure") or {}
    examples = ref.get("practical_examples") or []
    specs = ref.get("spec_refs") or []

    lines = [
        "## RRC setup failure — HARQ / MAC / PHY fault analysis",
        "",
        "RRC setup can fail at the **RRC layer** (reject, T300) or **below RRC** during RACH/Msg4/RRC Setup "
        "when HARQ-ACK, K1 timing, or RV retransmissions do not complete. This report covers the MAC/PHY angles.",
        "",
        "### 1. K1 configuration (PDSCH → HARQ-ACK timing)",
        "",
        k1.get("summary", ""),
        "",
        f"- **RRC IE:** `{k1.get('rrc_ie', '')}`",
        f"- **DCI field:** {k1.get('dci_field', '')}",
        f"- **RRC fail link:** {k1.get('rrc_fail_link', '')}",
        f"- **RAR note:** {k1.get('note_rar', '')}",
        "",
        "**Checks:**",
    ]
    for c in k1.get("checks") or []:
        lines.append(f"- {c}")

    lines.extend([
        "",
        "### 2. Redundancy version (RV) mechanism",
        "",
        rv.get("summary", ""),
        "",
        f"- **DCI field:** {rv.get('dci_field', '')}",
        f"- **Typical RV sequence:** {' → '.join(rv.get('typical_sequence') or [])}",
        f"- **3GPP:** {rv.get('table_ref', '')}",
        f"- **RRC fail link:** {rv.get('rrc_fail_link', '')}",
        "",
        "**Checks:**",
    ])
    for c in rv.get("checks") or []:
        lines.append(f"- {c}")

    lines.extend([
        "",
        "### 3. HARQ processor configuration",
        "",
        hp.get("summary", ""),
        "",
        f"- **RRC IE:** `{hp.get('rrc_ie', '')}`",
        f"- **Hybrid HARQ:** {hp.get('hybrid_note', '')}",
        f"- **RRC fail link:** {hp.get('rrc_fail_link', '')}",
        "",
        "**Checks:**",
    ])
    for c in hp.get("checks") or []:
        lines.append(f"- {c}")

    lines.extend([
        "",
        "### 4. Hybrid nature of HARQ",
        "",
        "NR HARQ is **hybrid** = **FEC (LDPC)** + **ARQ** with **soft combining** at MAC.",
        "- First TX sends RV0; NACK triggers retx with RV2→3→1 (typical) from the circular buffer.",
        "- Unlike LTE, **both DL and UL use asynchronous HARQ** — DCI always carries **HARQ process number**.",
        "- gNB/UE track process ID so retx can arrive out of order vs the original slot.",
        "",
        "### 5. Frame structure insights",
        "",
        fs.get("summary", ""),
        "",
        f"- **Topics:** {', '.join(fs.get('topics') or [])}",
        f"- **RRC fail link:** {fs.get('rrc_fail_link', '')}",
        "",
        "**Checks:**",
    ])
    for c in fs.get("checks") or []:
        lines.append(f"- {c}")

    lines.extend([
        "",
        "### 6. Practical examples and use cases",
        "",
        "| Scenario | Sequence | Log patterns |",
        "|----------|----------|--------------|",
    ])
    for ex in examples:
        seq = " → ".join(ex.get("sequence") or [])[:120]
        pats = ", ".join(ex.get("log_patterns") or [])[:80]
        lines.append(f"| {ex.get('title', ex.get('id', ''))} | {seq} | {pats} |")

    lines.extend([
        "",
        "### RACH → RRC setup HARQ timeline (SA CBRA)",
        "",
        "```",
        "Msg1 PRACH → Msg2 RAR (no K1, no UE HARQ-ACK)",
        "Msg3 PUSCH (RRC Setup Request) — harq=0, rv_idx, crc",
        "Msg4 PDSCH (contention resolution) → UE PUCCH HARQ-ACK (K1 from DCI)",
        "RRC Setup PDSCH → UE PUCCH HARQ-ACK → RRC Setup Complete",
        "```",
        "",
        "### Decision tree (test engineer)",
        "",
        "1. **RRC Reject in log?** → RRC/NAS cause (not HARQ) — check reject cause IE.",
        "2. **Msg3 OK, no Msg4 / no C-RNTI?** → contention / Msg4 scheduling.",
        "3. **Msg4 decoded, re-PRACH?** → Msg4 HARQ-ACK / K1 / PUCCH miss.",
        "4. **RRC Setup Request sent, no Setup Complete?** → RRC Setup PDSCH RV retx / T300.",
        "5. **Good RSRP, setup fail?** → K1, CORESET/search space, or core path (less common at PHY).",
        "",
        "### References",
        "",
    ])
    for url in ref.get("references") or []:
        lines.append(f"- {url}")
    if specs:
        lines.append(f"- 3GPP: {', '.join(specs)}")

    if log_text:
        scan = scan_log_for_harq_rrc_faults(log_text)
        formatted = format_log_harq_scan(scan)
        if formatted:
            lines.extend(["", formatted])

    return "\n".join(lines)


def explain_rrc_harq_fault_dict(query: str = "", *, log_text: str | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "query": query,
        "reference": load_harq_rrc_fault_reference(),
        "markdown": explain_rrc_harq_fault(query, log_text=log_text),
        "log_scan": scan_log_for_harq_rrc_faults(log_text) if log_text else None,
    }
