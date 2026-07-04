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


def _labeled_count(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype(str).str.strip() != "") & (series != "None")


def _kpis_from_pm(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    if "timestamp" in sub.columns:
        sub = sub.groupby(["timestamp", "cell_id"], as_index=False).agg({
            "ho_attempt": "sum",
            "rach_attempt": "sum",
            "ho_success": "sum",
            "rach_success": "sum",
            "dl_tp": "mean",
            "ul_tp": "mean",
            "cqi": "mean",
        })
    ho_att = float(sub["ho_attempt"].sum())
    rach_att = float(sub["rach_attempt"].sum())
    out = {
        "ho_success_rate": _safe_rate(float(sub["ho_success"].sum()), ho_att),
        "rach_success_rate": _safe_rate(float(sub["rach_success"].sum()), rach_att),
        "throughput_mbps": round(float(sub["dl_tp"].mean()), 2),
        "cqi": round(float(sub["cqi"].mean()), 2),
        "ho_attempt_total": int(ho_att),
        "rach_attempt_total": int(rach_att),
    }
    if "rsrp" in sub.columns:
        out["ss_rsrp"] = round(float(sub["rsrp"].mean()), 2)
    if "rsrq" in sub.columns:
        out["ss_rsrq"] = round(float(sub["rsrq"].mean()), 2)
    if "sinr" in sub.columns:
        out["ss_sinr"] = round(float(sub["sinr"].mean()), 2)
    return out


def _kpis_from_handover(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    counts = sub["failure_type"].value_counts()
    non_success = sub[sub["failure_type"] != "SUCCESS"]
    target_rsrp = round(float(non_success["rsrp"].mean()), 2) if len(non_success) else None
    out = {
        "ho_success_rate": _safe_rate(float(counts.get("SUCCESS", 0)), total),
        "ho_prep_fail_rate": _safe_rate(float(counts.get("PREP_FAILURE", 0)), total),
        "ho_exec_fail_rate": _safe_rate(float(counts.get("EXEC_FAILURE", 0)), total),
        "ho_too_late_rate": _safe_rate(float(counts.get("TOO_LATE_HO", 0)), total),
        "ho_too_early_rate": _safe_rate(float(counts.get("TOO_EARLY_HO", 0)), total),
        "ho_ping_pong_rate": _safe_rate(float(counts.get("PING_PONG", 0)), total),
        "ho_wrong_cell_rate": _safe_rate(float(counts.get("WRONG_CELL", 0)), total),
        "ho_xn_fail_rate": _safe_rate(float(counts.get("XN_FAILURE", 0)), total),
        "ho_n2_fail_rate": _safe_rate(float(counts.get("N2_FAILURE", 0)), total),
        "target_rsrp": target_rsrp,
        "ss_rsrp": round(float(sub["rsrp"].mean()), 2),
        "ss_sinr": round(float(sub["sinr"].mean()), 2),
        "ho_event_count": total,
    }
    if "rsrq" in sub.columns:
        out["ss_rsrq"] = round(float(sub["rsrq"].mean()), 2)
    return out
    if "rsrq" in sub.columns:
        out["ss_rsrq"] = round(float(sub["rsrq"].mean()), 2)
    return out


def _kpis_from_rlf(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    labeled = sub[_labeled_count(sub["cause"])]
    labeled_count = len(labeled)
    post_ho = _safe_rate(float((labeled["cause"] == "Post_HO").sum()), total)
    coverage = _safe_rate(float((labeled["cause"] == "Coverage").sum()), total)
    interference = _safe_rate(float((labeled["cause"] == "Interference").sum()), total)
    oos = int((sub["sinr"] < 0).sum())
    return {
        "rlf_rate": _safe_rate(float(labeled_count), total),
        "rlf_event_count": total,
        "rlf_coverage_pct": coverage,
        "rlf_post_ho_pct": post_ho,
        "rlf_after_ho_rate": post_ho,
        "rlf_interference_pct": interference,
        "rlf_rsrp_mean": round(float(sub["rsrp"].mean()), 2),
        "rlf_sinr_mean": round(float(sub["sinr"].mean()), 2),
        "out_of_sync_events": oos,
        "rlf_after_sync_fail": 1 if oos > 5 else 0,
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


def _kpis_from_call_drop(df: pd.DataFrame, cell_id: str, ho_event_count: float | None) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    labeled = sub[_labeled_count(sub["drop_type"])]
    drops = len(labeled) if len(labeled) > 0 else len(sub)
    counts = labeled["drop_type"].value_counts().to_dict() if len(labeled) > 0 else {}
    base = max(ho_event_count or 0, float(drops), 1.0)
    mobility = _safe_rate(float(counts.get("Mobility", 0)), drops)
    radio = _safe_rate(float(counts.get("Radio", 0)), drops)
    core = _safe_rate(float(counts.get("Core", 0)), drops)
    ims = _safe_rate(float(counts.get("IMS", 0)), drops)
    transport = _safe_rate(float(counts.get("Transport", 0)), drops)
    dominant = max(counts, key=counts.get) if counts else None
    return {
        "call_drop_rate": _safe_rate(float(drops), base),
        "call_drop_count": drops,
        "drop_mobility_pct": mobility,
        "drop_radio_pct": radio,
        "drop_core_pct": core,
        "drop_ims_pct": ims,
        "drop_transport_pct": transport,
        "ims_drop_rate": ims,
        "amf_release_rate": core,
        "dominant_drop_type": dominant,
    }


def _kpis_from_throughput(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    labeled = sub[_labeled_count(sub["issue"])]
    top_issue = labeled["issue"].value_counts().idxmax() if len(labeled) else "None"
    return {
        "throughput_mbps": round(float(sub["dl_tp"].mean()), 2),
        "cqi": round(float(sub["cqi"].mean()), 2),
        "prb_utilization": round(float(sub["prb_util"].mean()), 2),
        "throughput_top_issue": top_issue,
        "throughput_rf_issue_pct": _safe_rate(float((labeled["issue"] == "RF").sum()), len(labeled) or len(sub)),
        "throughput_congestion_pct": _safe_rate(float((labeled["issue"] == "Congestion").sum()), len(labeled) or len(sub)),
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
        if merged.get("ho_event_count"):
            rlf_k["rlf_rate"] = _safe_rate(
                float(rlf_k["rlf_event_count"]), float(merged["ho_event_count"])
            )
            merged["rlf_rate"] = rlf_k["rlf_rate"]
        if rlf_k.get("rlf_rsrp_mean") is not None:
            merged["ss_rsrp"] = rlf_k["rlf_rsrp_mean"]
        if rlf_k.get("rlf_sinr_mean") is not None:
            merged["ss_sinr"] = rlf_k["rlf_sinr_mean"]
        sources.append("rlf_events")

    rach = load_rach_events()
    rach_k = _kpis_from_rach(rach, cell_id)
    if rach_k:
        for k, v in rach_k.items():
            if k in ("rach_success_rate",) or k not in merged:
                merged[k] = v
        sources.append("rach_events")

    cd = load_call_drop_events()
    ho_events = merged.get("ho_event_count")
    cd_k = _kpis_from_call_drop(cd, cell_id, float(ho_events) if ho_events else None)
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
