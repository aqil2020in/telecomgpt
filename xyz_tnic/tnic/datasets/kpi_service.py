"""KPI calculation service — merges all telecom datasets per cell for RCA."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from tnic.datasets.loaders import (
    load_call_drop_events,
    load_handover_events,
    load_pm_counters,
    load_rach_events,
    load_rlf_events,
    load_throughput_metrics,
)
from tnic.datasets.models import CellKPIs, ClusterKPISummary
from tnic.models.schemas import KPIInput
from tnic.services.health_scoring import compute_health_score


def _safe_rate(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return round(100.0 * num / den, 2)


def _kpis_from_pm(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    ho_att = float(sub["ho_attempt"].sum())
    rach_att = float(sub["rach_attempt"].sum())
    return {
        "ho_success_rate": _safe_rate(float(sub["ho_success"].sum()), ho_att),
        "rach_success_rate": _safe_rate(float(sub["rach_success"].sum()), rach_att),
        "throughput_mbps": round(float(sub["dl_tp"].mean()), 2),
        "cqi": round(float(sub["cqi"].mean()), 2),
        "ho_attempt_total": int(ho_att),
        "rach_attempt_total": int(rach_att),
    }


def _kpis_from_handover(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    counts = sub["failure_type"].value_counts()
    return {
        "ho_success_rate": _safe_rate(float(counts.get("SUCCESS", 0)), total),
        "ho_prep_fail_rate": _safe_rate(float(counts.get("PREP_FAILURE", 0)), total),
        "ho_too_late_rate": _safe_rate(float(counts.get("TOO_LATE_HO", 0)), total),
        "ho_ping_pong_rate": _safe_rate(float(counts.get("PING_PONG", 0)), total),
        "ss_rsrp": round(float(sub["rsrp"].mean()), 2),
        "ss_sinr": round(float(sub["sinr"].mean()), 2),
        "ho_event_count": total,
    }


def _kpis_from_rlf(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    real = sub[sub["cause"] != "None"]
    return {
        "rlf_rate": _safe_rate(float(len(real)), total),
        "rlf_event_count": total,
        "rlf_coverage_pct": _safe_rate(float((sub["cause"] == "Coverage").sum()), total),
        "rlf_post_ho_pct": _safe_rate(float((sub["cause"] == "Post_HO").sum()), total),
        "rlf_interference_pct": _safe_rate(float((sub["cause"] == "Interference").sum()), total),
    }


def _kpis_from_rach(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    counts = sub["msg_failure"].value_counts()
    success = float(counts.get("SUCCESS", 0))
    return {
        "rach_success_rate": _safe_rate(success, total),
        "rach_msg1_fail_rate": _safe_rate(float(counts.get("MSG1", 0)), total),
        "rach_msg2_fail_rate": _safe_rate(float(counts.get("MSG2", 0)), total),
        "rach_msg3_fail_rate": _safe_rate(float(counts.get("MSG3", 0)), total),
        "rach_msg4_fail_rate": _safe_rate(float(counts.get("MSG4", 0)), total),
        "rach_event_count": total,
    }


def _kpis_from_call_drop(df: pd.DataFrame, cell_id: str, ho_attempts: float | None) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    drops = len(sub)
    counts = sub["drop_type"].value_counts().to_dict()
    base = ho_attempts if ho_attempts and ho_attempts > 0 else float(drops)
    return {
        "call_drop_rate": _safe_rate(float(drops), base),
        "call_drop_count": drops,
        "drop_mobility_pct": _safe_rate(float(counts.get("Mobility", 0)), drops),
        "drop_radio_pct": _safe_rate(float(counts.get("Radio", 0)), drops),
        "drop_core_pct": _safe_rate(float(counts.get("Core", 0)), drops),
        "drop_ims_pct": _safe_rate(float(counts.get("IMS", 0)), drops),
    }


def _kpis_from_throughput(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    top_issue = sub["issue"].value_counts().idxmax() if len(sub) else "None"
    return {
        "throughput_mbps": round(float(sub["dl_tp"].mean()), 2),
        "cqi": round(float(sub["cqi"].mean()), 2),
        "prb_utilization": round(float(sub["prb_util"].mean()), 2),
        "throughput_top_issue": top_issue,
        "throughput_rf_issue_pct": _safe_rate(float((sub["issue"] == "RF").sum()), len(sub)),
        "throughput_congestion_pct": _safe_rate(float((sub["issue"] == "Congestion").sum()), len(sub)),
    }


def list_cell_ids() -> list[str]:
    cells: set[str] = set()
    for loader in (
        load_pm_counters, load_handover_events, load_rlf_events,
        load_rach_events, load_call_drop_events, load_throughput_metrics,
    ):
        try:
            df = loader()
            if "cell_id" in df.columns:
                cells.update(df["cell_id"].unique().tolist())
        except FileNotFoundError:
            continue
    return sorted(cells)


def compute_cell_kpis(cell_id: str) -> CellKPIs:
    sources: list[str] = []
    merged: dict[str, Any] = {"cell_id": cell_id}

    pm = load_pm_counters()
    pm_k = _kpis_from_pm(pm, cell_id)
    if pm_k:
        merged.update(pm_k)
        sources.append("pm_counters")

    ho = load_handover_events()
    ho_k = _kpis_from_handover(ho, cell_id)
    if ho_k:
        for k, v in ho_k.items():
            if k not in merged or merged[k] is None:
                merged[k] = v
        sources.append("handover_events")

    rlf = load_rlf_events()
    rlf_k = _kpis_from_rlf(rlf, cell_id)
    if rlf_k:
        merged.update(rlf_k)
        sources.append("rlf_events")

    rach = load_rach_events()
    rach_k = _kpis_from_rach(rach, cell_id)
    if rach_k:
        for k, v in rach_k.items():
            if k in ("rach_success_rate",) or k not in merged:
                merged[k] = v
        sources.append("rach_events")

    cd = load_call_drop_events()
    ho_base = merged.get("ho_attempt_total")
    cd_k = _kpis_from_call_drop(cd, cell_id, float(ho_base) if ho_base else None)
    if cd_k:
        merged.update(cd_k)
        sources.append("call_drop_events")

    tp = load_throughput_metrics()
    tp_k = _kpis_from_throughput(tp, cell_id)
    if tp_k:
        for k, v in tp_k.items():
            if k in ("throughput_mbps", "cqi", "prb_utilization") or k not in merged:
                merged[k] = v
        sources.append("throughput_metrics")

    health = compute_health_score(merged)
    return CellKPIs(
        cell_id=cell_id,
        kpis=merged,
        sources=sources,
        health_score=health["overall_score"],
    )


def compute_cluster_kpis() -> ClusterKPISummary:
    cells = list_cell_ids()
    result: dict[str, CellKPIs] = {}
    for cid in cells:
        result[cid] = compute_cell_kpis(cid)
    worst = sorted(cells, key=lambda c: result[c].health_score or 100)[:5]
    return ClusterKPISummary(cell_count=len(cells), cells=result, worst_cells=worst)


def build_kpi_input(cell_id: str | None = None, query: str = "") -> KPIInput:
    cid = cell_id or extract_cell_id(query) or pick_worst_cell()
    bundle = compute_cell_kpis(cid)
    fields = KPIInput.model_fields
    payload = {k: v for k, v in bundle.kpis.items() if k in fields and v is not None}
    payload["cell_id"] = cid
    extra = {k: v for k, v in bundle.kpis.items() if k not in fields}
    if extra:
        payload["extra"] = extra
    return KPIInput(**payload)


def extract_cell_id(query: str) -> str | None:
    m = re.search(r"\b(XYZ\d{3,4}|432\d{2})\b", query, re.I)
    return m.group(1).upper() if m else None


def pick_worst_cell() -> str:
    cluster = compute_cluster_kpis()
    if cluster.worst_cells:
        return cluster.worst_cells[0]
    cells = list_cell_ids()
    return cells[0] if cells else "UNKNOWN"


def kpis_for_rca(query: str = "", cell_id: str | None = None) -> dict[str, Any]:
    """Return merged KPI dict for orchestrator/agents."""
    bundle = compute_cell_kpis(cell_id or extract_cell_id(query) or pick_worst_cell())
    return bundle.kpis
