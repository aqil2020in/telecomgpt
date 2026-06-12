"""ShareTechnote RF Handbook reference loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REF = Path(__file__).resolve().parent.parent / "data" / "rf_handbook_reference.json"


def load_rf_handbook_reference() -> dict[str, Any]:
    if not _REF.exists():
        return {}
    return json.loads(_REF.read_text(encoding="utf-8"))


def lookup_rf_topics(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Match handbook topics by keyword in query."""
    ref = load_rf_handbook_reference()
    ql = query.lower()
    hits: list[tuple[int, dict[str, Any]]] = []

    if any(k in ql for k in ("power class", "powerclass", "hpue", "pc2", "pc3", "redcap")):
        pc = ref.get("nr_power_class")
        if pc:
            hits.append((6, {
                "id": "nr_power_class",
                "title": "NR UE Power Class",
                "url": pc.get("url"),
                "summary": pc.get("summary"),
                "test_use": pc.get("test_use"),
                "category": "5G NR RF",
            }))

    for cat in ref.get("categories", []):
        for topic in cat.get("topics", []):
            score = 0
            blob = " ".join(
                str(topic.get(k, "")) for k in ("id", "title", "summary", "test_use")
            ).lower()
            for token in ql.replace("/", " ").replace("-", " ").split():
                if len(token) < 3:
                    continue
                if token in blob:
                    score += 2
                if token in topic.get("id", "").lower():
                    score += 3
            for kpi in topic.get("related_kpis") or []:
                if kpi.replace("_", " ") in ql or kpi in ql:
                    score += 4
            if score:
                hits.append((score, {**topic, "category": cat.get("label")}))

    cross = ref.get("kpi_crosswalk") or {}
    for kpi_id, meta in cross.items():
        if kpi_id in ql or kpi_id.replace("_", " ") in ql:
            for tid in meta.get("topics", []):
                for cat in ref.get("categories", []):
                    for topic in cat.get("topics", []):
                        if topic.get("id") == tid:
                            hits.append((5, {**topic, "category": cat.get("label"), "kpi_note": meta.get("note")}))

    hits.sort(key=lambda x: -x[0])
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for _, topic in hits:
        tid = topic.get("id") or topic.get("url")
        if tid in seen:
            continue
        seen.add(tid)
        out.append(topic)
        if len(out) >= limit:
            break
    return out


def format_rf_handbook_hints(query: str) -> str:
    topics = lookup_rf_topics(query)
    if not topics:
        return ""
    ref = load_rf_handbook_reference()
    lines = ["**RF Handbook (ShareTechnote)**"]
    for t in topics:
        lines.append(f"- [{t.get('title')}]({t.get('url')}) — {t.get('test_use') or t.get('summary', '')[:120]}")
    if ref.get("index_url"):
        lines.append(f"\nFull index: {ref['index_url']}")
    return "\n".join(lines)
