"""NR UE Power Class reference — ShareTechnote / TS 38.101."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REF = Path(__file__).resolve().parent.parent / "data" / "nr_power_class_reference.json"
_BAND_RE = re.compile(r"\bn(\d{1,3})\b", re.I)
_PC_RE = re.compile(r"\b(?:power\s*class|pc|hpue)\s*([1234567]|1\.5)\b", re.I)


def load_power_class_reference() -> dict[str, Any]:
    if not _REF.exists():
        return {}
    return json.loads(_REF.read_text(encoding="utf-8"))


def lookup_power_class(query: str) -> dict[str, Any]:
    """Return FR1/FR2 class info matching query tokens (band, class number, HPUE)."""
    ref = load_power_class_reference()
    ql = query.lower()
    bands = [f"n{m.group(1)}" for m in _BAND_RE.finditer(query)]
    pc_match = _PC_RE.search(query)
    pc_num = pc_match.group(1) if pc_match else None

    fr1_hits = []
    for cls in ref.get("fr1", {}).get("classes", []):
        score = 0
        if pc_num and pc_num.replace(".", "_") in cls.get("id", "").replace("pc", ""):
            score += 5
        if "hpue" in ql and cls.get("id") in ("pc2", "pc1_5"):
            score += 4
        if "smartphone" in ql and cls.get("id") == "pc3":
            score += 3
        if "default" in ql and cls.get("id") == "pc3":
            score += 3
        for b in bands:
            if b in (cls.get("bands") or []) or b in (cls.get("bands_note") or ""):
                score += 3
        if "fr1" in ql or any(b in ql for b in ("n77", "n78", "n41", "n28")):
            score += 1
        if score:
            fr1_hits.append((score, cls))

    fr2_hits = []
    for cls in ref.get("fr2", {}).get("classes", []):
        score = 0
        cid = cls.get("id", "").replace("pc", "")
        if pc_num and pc_num == cid:
            score += 5
        if "redcap" in ql and cls.get("id") == "pc7":
            score += 5
        if "mmwave" in ql or "fr2" in ql:
            score += 2
        if "fwa" in ql and cls.get("id") in ("pc1", "pc5"):
            score += 3
        if "handheld" in ql and cls.get("id") == "pc3":
            score += 3
        for b in bands:
            if b in (cls.get("bands") or []):
                score += 3
        if score:
            fr2_hits.append((score, cls))

    fr1_hits.sort(key=lambda x: -x[0])
    fr2_hits.sort(key=lambda x: -x[0])

    return {
        "reference": ref.get("reference"),
        "spec_refs": ref.get("spec_refs", []),
        "bands_queried": bands,
        "fr1_matches": [c for _, c in fr1_hits[:3]],
        "fr2_matches": [c for _, c in fr2_hits[:3]],
        "default_fr1": ref.get("fr1", {}).get("default_class"),
    }


def format_power_class_brief(query: str) -> str:
    ref = load_power_class_reference()
    if not ref:
        return ""
    ql = query.lower()
    if not any(k in ql for k in (
        "power class", "powerclass", "hpue", "pc1", "pc2", "pc3", "pc7",
        "redcap", "max power", "23 dbm", "26 dbm", "eirp", "trp",
    )) and not _BAND_RE.search(query) and not _PC_RE.search(query):
        return ""

    lookup = lookup_power_class(query)
    lines = ["**NR Power Class** ([ShareTechnote]({}))".format(ref.get("reference", ""))]

    if lookup.get("fr1_matches"):
        lines.append("**FR1:**")
        for c in lookup["fr1_matches"]:
            mp = c.get("max_power_dbm")
            lines.append(f"- {c.get('label')}: {mp} dBm max — {c.get('use_case')}")
    elif "fr1" in ql or any(b in ql for b in ("n77", "n78")):
        lines.append("- FR1 default: **Power Class 3** (23 dBm) on all bands")

    if lookup.get("fr2_matches"):
        lines.append("**FR2:**")
        for c in lookup["fr2_matches"]:
            lines.append(f"- {c.get('label')}: {c.get('use_case')} (max EIRP {c.get('max_eirp_dbm')} dBm)")

    lines.append(f"Specs: {', '.join(ref.get('spec_refs', [])[:2])}")
    return "\n".join(lines)
