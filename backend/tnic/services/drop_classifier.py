"""Call drop root-cause classification from event KPI breakdown."""

from __future__ import annotations

from typing import Any


def classify_drop_causes(kpis: dict[str, Any]) -> dict[str, Any]:
    breakdown = {
        "Mobility": float(kpis.get("drop_mobility_pct") or 0),
        "IMS": float(kpis.get("drop_ims_pct") or 0),
        "Radio": float(kpis.get("drop_radio_pct") or 0),
        "Core": float(kpis.get("drop_core_pct") or 0),
        "Transport": float(kpis.get("drop_transport_pct") or 0),
    }
    active = {k: v for k, v in breakdown.items() if v > 0}
    if not active:
        return {
            "primary": "Unknown",
            "confidence": 0.5,
            "breakdown": breakdown,
            "summary": "No labeled call drop events available for classification.",
        }
    primary = max(active, key=active.get)
    confidence = min(0.95, round(0.55 + active[primary] / 200, 2))
    count = int(kpis.get("call_drop_count") or 0)
    if count >= 50:
        confidence = min(0.95, confidence + 0.05)
    elif count < 20:
        confidence = max(0.45, confidence - 0.08)
    parts = ", ".join(f"{k} {v:.1f}%" for k, v in sorted(active.items(), key=lambda x: -x[1]))
    return {
        "primary": primary,
        "confidence": confidence,
        "breakdown": breakdown,
        "summary": f"Primary drop class: **{primary}** ({active[primary]:.1f}%). Mix: {parts}.",
    }


def drop_classification_finding(kpis: dict[str, Any]) -> dict[str, Any] | None:
    result = classify_drop_causes(kpis)
    if result["primary"] == "Unknown":
        return None
    return {
        "rule_id": "drop_root_cause_class",
        "category": "call_drop",
        "probable_cause": result["summary"],
        "confidence": result["confidence"],
        "evidence": {
            "dominant_drop_type": result["primary"],
            "breakdown": result["breakdown"],
            "call_drop_count": kpis.get("call_drop_count"),
        },
        "recommended_actions": [
            f"Investigate {result['primary']} drop sub-workflow",
            "Correlate with PM counters and neighbor HO/RLF events",
            "Validate fix over 48h monitoring window",
        ],
    }
