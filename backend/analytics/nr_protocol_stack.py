"""NR radio protocol stack reference — ShareTechnote / 3GPP layer map."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REF = Path(__file__).resolve().parent.parent / "data" / "nr_protocol_stack_reference.json"

_LAYER_KW = {
    "phy": ["phy", "physical", "ssb", "prach", "pdcch", "pdsch", "pusch", "pucch", "mimo", "beam"],
    "mac": ["mac", "harq", "rach", "scheduling", "bsr"],
    "rlc": ["rlc", "am mode", "um mode", "reassembly"],
    "pdcp": ["pdcp", "cipher", "integrity", "rohc"],
    "sdap": ["sdap", "qos flow", "qfi", "5qi"],
    "rrc": ["rrc", "reconfiguration", "measurement", "srb", "drb"],
    "nas": ["nas", "5gmm", "5gsm", "registration", "pdu session", "authentication"],
}


def load_protocol_stack_reference() -> dict[str, Any]:
    if not _REF.exists():
        return {}
    return json.loads(_REF.read_text(encoding="utf-8"))


def lookup_layers(query: str) -> list[dict[str, Any]]:
    ref = load_protocol_stack_reference()
    ql = query.lower()
    hits: list[tuple[int, dict[str, Any]]] = []

    if any(k in ql for k in ("protocol stack", "stack architecture", "radio stack", "layer 2", "l2 stack")):
        hits.append((10, {"id": "overview", "name": "NR Protocol Stack", "summary": ref.get("overview")}))

    for layer in ref.get("layers", []):
        score = 0
        lid = layer.get("id", "")
        if lid in ql or layer.get("name", "").lower() in ql:
            score += 8
        for kw in _LAYER_KW.get(lid, []):
            if kw in ql:
                score += 4
        if score:
            hits.append((score, layer))

    if any(k in ql for k in ("c-plane", "c plane", "control plane", "signaling")):
        hits.append((6, {"id": "c_plane", **ref.get("planes", {}).get("c_plane", {})}))
    if any(k in ql for k in ("u-plane", "u plane", "user plane", "data plane", "throughput")):
        hits.append((6, {"id": "u_plane", **ref.get("planes", {}).get("u_plane", {})}))

    hits.sort(key=lambda x: -x[0])
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for _, item in hits:
        iid = item.get("id") or item.get("name", "")
        if iid in seen:
            continue
        seen.add(iid)
        out.append(item)
    return out[:6]


def detect_stack_layers_in_log(log_text: str) -> dict[str, bool]:
    ref = load_protocol_stack_reference()
    patterns = ref.get("log_layer_patterns") or {}
    lower = log_text.lower()
    return {
        layer: any(p.lower() in lower or re.search(p, log_text, re.I) for p in pats)
        for layer, pats in patterns.items()
    }


def format_protocol_stack_brief(query: str) -> str:
    ref = load_protocol_stack_reference()
    if not ref:
        return ""
    ql = query.lower()
    triggers = (
        "protocol stack", "stack architecture", "radio stack", "c-plane", "u-plane",
        "user plane", "control plane", " pdcp", " rlc", " sdap", " 5gmm", "layer 2",
    )
    if not any(t.strip() in ql for t in triggers) and not lookup_layers(query):
        return ""

    lines = [
        f"**NR Protocol Stack** ([ShareTechnote]({ref.get('reference', '')}))",
        ref.get("overview", ""),
    ]
    planes = ref.get("planes", {})
    if planes.get("u_plane"):
        up = planes["u_plane"]
        lines.append(f"- **U-Plane:** {' → '.join(up.get('stack_bottom_up', []))} → {up.get('top_connection', '')}")
    if planes.get("c_plane"):
        cp = planes["c_plane"]
        lines.append(f"- **C-Plane:** {' → '.join(cp.get('stack_bottom_up', []))} → {cp.get('top_connection', '')}")

    layers = lookup_layers(query)
    if layers:
        lines.append("**Relevant layers:**")
        for ly in layers[:4]:
            spec = ly.get("spec") or ", ".join(ly.get("specs") or [])
            lines.append(f"- {ly.get('name', ly.get('id'))}: {spec}" + (f" — {ly.get('test_use')}" if ly.get("test_use") else ""))

    cheatsheet = ref.get("spec_cheatsheet", {}).get("access_stratum", {})
    if cheatsheet and any(k in ql for k in ("spec", "3gpp", "ts 38", "ts 24")):
        lines.append("**Access stratum specs:** " + ", ".join(f"{k}={v}" if isinstance(v, str) else k for k, v in list(cheatsheet.items())[:5]))

    return "\n".join(lines)


def format_log_stack_scan(log_text: str) -> str:
    detected = detect_stack_layers_in_log(log_text)
    if not any(detected.values()):
        return ""
    lines = ["**Protocol stack layers detected in log:**"]
    for layer, found in detected.items():
        lines.append(f"- {layer}: {'✓' if found else '—'}")
    return "\n".join(lines)
