"""Cell / network health scoring engine."""

from __future__ import annotations

from typing import Any


def _score_higher_better(val: float | None, good: float, fair: float) -> float:
    if val is None:
        return 70.0
    if val >= good:
        return 95.0
    if val >= fair:
        return 75.0
    return max(30.0, 50.0 + (val - fair) * 2)


def _score_lower_better(val: float | None, good: float, fair: float) -> float:
    if val is None:
        return 70.0
    if val <= good:
        return 95.0
    if val <= fair:
        return 75.0
    return max(25.0, 80.0 - val)


def compute_health_score(kpis: dict[str, Any]) -> dict[str, Any]:
    dimensions = {
        "rf": _score_higher_better(kpis.get("ss_sinr"), 13, 5),
        "coverage": _score_higher_better(kpis.get("ss_rsrp"), -85, -100),
        "throughput": _score_higher_better(kpis.get("throughput_mbps"), 100, 30),
        "mobility": _score_higher_better(kpis.get("ho_success_rate"), 98, 95),
        "access": _score_higher_better(kpis.get("rach_success_rate"), 98, 92),
        "reliability": _score_lower_better(kpis.get("call_drop_rate"), 1, 3),
        "latency": _score_lower_better(kpis.get("latency_ms") or kpis.get("upf_latency_ms"), 30, 60),
        "beam": _score_lower_better(kpis.get("beam_failure_ratio"), 10, 25),
    }
    weights = {"rf": 0.15, "coverage": 0.15, "throughput": 0.15, "mobility": 0.15,
               "access": 0.1, "reliability": 0.15, "latency": 0.1, "beam": 0.05}
    overall = sum(dimensions[k] * weights[k] for k in dimensions)
    grade = "A" if overall >= 85 else "B" if overall >= 70 else "C" if overall >= 55 else "D"
    alerts = []
    if dimensions["mobility"] < 60:
        alerts.append("Mobility health critical — review HO KPIs")
    if dimensions["reliability"] < 60:
        alerts.append("Drop rate elevated — run call drop RCA")
    if dimensions["throughput"] < 60:
        alerts.append("Throughput dimension degraded")
    return {
        "overall_score": round(overall, 1),
        "grade": grade,
        "dimensions": {k: round(v, 1) for k, v in dimensions.items()},
        "alerts": alerts,
    }


def cell_health_response(cell_id: str, kpis: dict[str, Any]) -> dict[str, Any]:
    h = compute_health_score(kpis)
    return {"cell_id": cell_id, **h}
