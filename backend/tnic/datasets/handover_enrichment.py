"""Transform raw handover_events.csv into RCA-ready enriched events.

Derives mobility, RF, transport, and failure-stage columns while preserving
original ue_id, cell_id, rsrp, sinr, failure_type for backward compatibility.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.registry import DatasetName, dataset_path, datasets_dir

# Original failure_type -> standardized failure_stage
FAILURE_STAGE_MAP: dict[str, str] = {
    "PREP_FAILURE": "HO_PREPARATION",
    "EXEC_FAILURE": "HO_EXECUTION",
    "PING_PONG": "POST_HO",
    "TOO_LATE_HO": "HO_DECISION",
    "TOO_EARLY_HO": "HO_DECISION",
    "SUCCESS": "SUCCESS",
    "WRONG_CELL": "HO_EXECUTION",
    "XN_FAILURE": "HO_PREPARATION",
    "N2_FAILURE": "HO_PREPARATION",
}

HO_TYPE_MAP: dict[str, str] = {
    "XN_FAILURE": "INTER_GNB_XN",
    "N2_FAILURE": "INTER_GNB_NG",
    "PREP_FAILURE": "INTRA_NR",
    "EXEC_FAILURE": "INTRA_NR",
    "PING_PONG": "INTRA_NR",
    "TOO_EARLY_HO": "INTRA_NR",
    "TOO_LATE_HO": "INTRA_NR",
    "WRONG_CELL": "INTRA_NR",
    "SUCCESS": "INTRA_NR",
}

MEASUREMENT_EVENT_MAP: dict[str, str] = {
    "TOO_EARLY_HO": "A3",
    "TOO_LATE_HO": "A5",
    "PING_PONG": "A3",
    "WRONG_CELL": "A3",
    "SUCCESS": "A3",
    "PREP_FAILURE": "A3",
    "EXEC_FAILURE": "A3",
    "XN_FAILURE": "A3",
    "N2_FAILURE": "A3",
}

RCA_SCENARIOS = (
    "handover_preparation_failure",
    "handover_execution_failure",
    "too_early_handover",
    "too_late_handover",
    "ping_pong_handover",
    "missing_neighbor",
    "xn_transport_failure",
    "post_ho_rlf",
    "coverage_induced_ho_failure",
    "interference_induced_ho_failure",
    "beam_instability",
    "mobility_configuration_issue",
)

_CELL_NUM_RE = re.compile(r"(\d+)$")


def _stable_int(key: str, mod: int, offset: int = 0) -> int:
    h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
    return offset + (h % mod)


def _cell_numeric(cell_id: str) -> int:
    m = _CELL_NUM_RE.search(str(cell_id))
    return int(m.group(1)) if m else 401


def _default_pci(cell_id: str) -> int:
    return 100 + (_cell_numeric(cell_id) % 200)


def _default_mobility_params(cell_id: str) -> dict[str, float | int]:
    n = _cell_numeric(cell_id)
    return {
        "pci": _default_pci(cell_id),
        "a3_offset": -3 + (n % 5),
        "hysteresis": n % 3,
        "time_to_trigger": 40 + (n % 4) * 40,
        "neighbor_count": 4 + (n % 8),
    }


def _load_cell_config() -> dict[str, dict[str, Any]]:
    path = datasets_dir() / "cell_configuration.csv"
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    for _, row in df.iterrows():
        cid = str(row["cell_id"])
        out[cid] = {
            "pci": int(row.get("pci", _default_pci(cid))),
            "a3_offset": float(row.get("a3_offset", 0)),
            "hysteresis": float(row.get("hysteresis", 0)),
            "time_to_trigger": int(row.get("time_to_trigger", 40)),
            "neighbor_count": int(row.get("neighbor_count", 5)),
        }
    return out


def _load_neighbor_map() -> dict[str, list[tuple[str, str]]]:
    """source_cell -> [(target_cell, relation_status), ...]"""
    path = datasets_dir() / "neighbor_relations.csv"
    out: dict[str, list[tuple[str, str]]] = {}
    if not path.exists():
        return out
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    for _, row in df.iterrows():
        src = str(row["source_cell"])
        tgt = str(row["target_cell"])
        status = str(row.get("relation_status", "ACTIVE")).upper()
        out.setdefault(src, []).append((tgt, status))
    return out


def _synthetic_neighbors(source_cell: str, all_cells: list[str]) -> list[tuple[str, str]]:
    src_n = _cell_numeric(source_cell)
    neighbors: list[tuple[str, str]] = []
    for c in all_cells:
        if c == source_cell:
            continue
        diff = abs(_cell_numeric(c) - src_n)
        if diff <= 2:
            status = "MISSING" if diff == 2 and src_n % 3 == 0 else "ACTIVE"
            neighbors.append((c, status))
    if not neighbors:
        alt = f"XYZ{src_n + 1}" if src_n < 410 else f"XYZ{src_n - 1}"
        neighbors.append((alt, "ACTIVE"))
    return neighbors


def _pick_target(
    source_cell: str,
    failure_type: str,
    ue_id: str,
    row_idx: int,
    neighbor_map: dict[str, list[tuple[str, str]]],
    all_cells: list[str],
) -> tuple[str, str, bool]:
    """Return (target_cell, relation_status, is_missing_neighbor)."""
    candidates = neighbor_map.get(source_cell) or _synthetic_neighbors(source_cell, all_cells)
    if failure_type in ("PREP_FAILURE", "XN_FAILURE") and any(s == "MISSING" for _, s in candidates):
        for tgt, status in candidates:
            if status == "MISSING":
                return tgt, status, True
    if failure_type == "WRONG_CELL":
        # Suboptimal / wrong ranked neighbor
        idx = _stable_int(f"{ue_id}:{row_idx}:wrong", len(candidates))
        tgt, status = candidates[idx]
        return tgt, status, status == "MISSING"
    idx = _stable_int(f"{ue_id}:{row_idx}", len(candidates))
    tgt, status = candidates[idx]
    missing = status == "MISSING" or (
        failure_type == "PREP_FAILURE" and _stable_int(f"{ue_id}:missing", 100) < 18
    )
    if missing and status != "MISSING":
        status = "MISSING"
    return tgt, status, status == "MISSING" or missing


def _rsrq_from_rsrp_sinr(rsrp: float, sinr: float) -> float:
    """Approximate SS-RSRQ (dB) from RSRP and SINR."""
    return round(rsrp - max(0.0, 15.0 - sinr) - 3.0, 1)


def _target_rf(
    serving_rsrp: float,
    serving_sinr: float,
    failure_type: str,
    ue_id: str,
    row_idx: int,
) -> tuple[float, float]:
    seed = _stable_int(f"{ue_id}:{row_idx}:rf", 100)
    if failure_type == "SUCCESS":
        delta = 2 + (seed % 5)
    elif failure_type in ("TOO_LATE_HO", "PREP_FAILURE", "XN_FAILURE"):
        delta = -8 - (seed % 12)
    elif failure_type == "TOO_EARLY_HO":
        delta = 6 + (seed % 8)
    elif failure_type == "PING_PONG":
        delta = (seed % 7) - 3
    elif failure_type == "WRONG_CELL":
        delta = -15 - (seed % 10)
    else:
        delta = -5 - (seed % 8)
    target_rsrp = round(serving_rsrp + delta, 1)
    sinr_delta = -2 if failure_type != "SUCCESS" else 1
    if failure_type == "WRONG_CELL":
        sinr_delta = -8
    target_sinr = round(serving_sinr + sinr_delta - (seed % 3), 1)
    return target_rsrp, target_sinr


def _speed_kmph(failure_type: str, ue_id: str, row_idx: int) -> float:
    base = {
        "SUCCESS": 35,
        "TOO_EARLY_HO": 85,
        "TOO_LATE_HO": 15,
        "PING_PONG": 55,
        "PREP_FAILURE": 45,
        "XN_FAILURE": 50,
        "N2_FAILURE": 48,
        "WRONG_CELL": 40,
        "EXEC_FAILURE": 38,
    }.get(failure_type, 40)
    jitter = _stable_int(f"{ue_id}:spd", 21) - 10
    return float(max(0, base + jitter))


def _xn_latency_ms(failure_type: str, ue_id: str, row_idx: int) -> float | None:
    if failure_type == "XN_FAILURE":
        return float(120 + _stable_int(f"{ue_id}:xn", 180))
    if failure_type == "PREP_FAILURE" and _stable_int(f"{ue_id}:xnlat", 100) < 25:
        return float(80 + _stable_int(f"{ue_id}:xn2", 60))
    if failure_type == "SUCCESS":
        return float(15 + _stable_int(f"{ue_id}:xnok", 25))
    return float(25 + _stable_int(f"{ue_id}:xn3", 40))


def _packet_loss_pct(failure_type: str, ue_id: str) -> float:
    if failure_type in ("XN_FAILURE", "N2_FAILURE", "PREP_FAILURE"):
        return round(1.5 + _stable_int(f"{ue_id}:pl", 80) / 10.0, 2)
    if failure_type in ("PING_PONG", "EXEC_FAILURE", "WRONG_CELL"):
        return round(0.3 + _stable_int(f"{ue_id}:pl2", 30) / 10.0, 2)
    return round(_stable_int(f"{ue_id}:pl3", 10) / 20.0, 2)


def _rlf_flags(failure_type: str, failure_stage: str, ue_id: str) -> tuple[bool, bool]:
    if failure_type == "PING_PONG" or failure_stage == "POST_HO":
        return True, _stable_int(f"{ue_id}:rlf", 100) < 45
    if failure_type in ("EXEC_FAILURE", "WRONG_CELL", "TOO_LATE_HO"):
        return _stable_int(f"{ue_id}:t310", 100) < 35, _stable_int(f"{ue_id}:rlf2", 100) < 30
    return False, False


def classify_rca_scenarios(row: dict[str, Any]) -> list[str]:
    """Return applicable RCA scenario tags for one enriched event."""
    ft = str(row.get("failure_type", "")).upper()
    stage = str(row.get("failure_stage", ""))
    scenarios: list[str] = []

    if ft in ("PREP_FAILURE", "XN_FAILURE", "N2_FAILURE") or stage == "HO_PREPARATION":
        scenarios.append("handover_preparation_failure")
    if ft in ("EXEC_FAILURE", "WRONG_CELL") or stage == "HO_EXECUTION":
        scenarios.append("handover_execution_failure")
    if ft == "TOO_EARLY_HO":
        scenarios.append("too_early_handover")
        scenarios.append("mobility_configuration_issue")
    if ft == "TOO_LATE_HO":
        scenarios.append("too_late_handover")
        scenarios.append("mobility_configuration_issue")
    if ft == "PING_PONG":
        scenarios.append("ping_pong_handover")
        scenarios.append("mobility_configuration_issue")
    if row.get("missing_neighbor") or row.get("neighbor_relation_status") == "MISSING":
        scenarios.append("missing_neighbor")
    if ft == "XN_FAILURE" or (row.get("xn_latency_ms") or 0) > 100:
        scenarios.append("xn_transport_failure")
    if row.get("rlf_detected") or (stage == "POST_HO" and row.get("t310_expiry")):
        scenarios.append("post_ho_rlf")
    target_rsrp = row.get("target_rsrp")
    serving_rsrp = row.get("serving_rsrp")
    if ft != "SUCCESS" and (
        (target_rsrp is not None and float(target_rsrp) < -110)
        or (serving_rsrp is not None and float(serving_rsrp) < -112)
    ):
        scenarios.append("coverage_induced_ho_failure")
    serving_sinr = row.get("serving_sinr")
    if ft != "SUCCESS" and serving_sinr is not None and float(serving_sinr) < 0:
        scenarios.append("interference_induced_ho_failure")
    if ft == "PING_PONG" and row.get("beam_id") != row.get("beam_id_target"):
        scenarios.append("beam_instability")
    if ft in ("TOO_EARLY_HO", "TOO_LATE_HO", "PING_PONG"):
        if not any(s == "mobility_configuration_issue" for s in scenarios):
            scenarios.append("mobility_configuration_issue")

    # dedupe preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for s in scenarios:
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    return ordered


def enrich_handover_events(
    df: pd.DataFrame,
    *,
    base_time: datetime | None = None,
) -> pd.DataFrame:
    """Derive RCA columns; preserve original five columns."""
    if df.empty:
        return df.copy()

    work = df.copy()
    work.columns = [c.strip().lower() for c in work.columns]
    for col in ("ue_id", "cell_id", "rsrp", "sinr", "failure_type"):
        if col not in work.columns:
            raise ValueError(f"handover_events missing required column: {col}")

    config = _load_cell_config()
    neighbor_map = _load_neighbor_map()
    all_cells = sorted(work["cell_id"].astype(str).unique().tolist())
    t0 = base_time or datetime(2026, 7, 1, 8, 0, 0, tzinfo=timezone.utc)

    rows: list[dict[str, Any]] = []
    for idx, raw in work.iterrows():
        ue_id = str(raw["ue_id"])
        source_cell = str(raw["cell_id"])
        failure_type = str(raw["failure_type"]).upper()
        serving_rsrp = float(raw["rsrp"])
        serving_sinr = float(raw["sinr"])

        cfg = config.get(source_cell, _default_mobility_params(source_cell))
        target_cell, rel_status, missing_nbr = _pick_target(
            source_cell, failure_type, ue_id, int(idx), neighbor_map, all_cells,
        )
        target_rsrp, target_sinr = _target_rf(serving_rsrp, serving_sinr, failure_type, ue_id, int(idx))
        serving_rsrq = _rsrq_from_rsrp_sinr(serving_rsrp, serving_sinr)
        target_rsrq = _rsrq_from_rsrp_sinr(target_rsrp, target_sinr)
        failure_stage = FAILURE_STAGE_MAP.get(failure_type, "HO_EXECUTION")
        t310_expiry, rlf_detected = _rlf_flags(failure_type, failure_stage, ue_id)
        pci_source = int(cfg.get("pci", _default_pci(source_cell)))
        pci_target = _default_pci(target_cell)
        beam_source = 1 + (_stable_int(f"{ue_id}:beam", 8))
        beam_target = beam_source if failure_type == "SUCCESS" else 1 + (_stable_int(f"{ue_id}:beamt", 8))

        ts = t0 + timedelta(seconds=int(idx) * 37 + _stable_int(ue_id, 300))
        enriched: dict[str, Any] = {
            # originals
            "ue_id": ue_id,
            "cell_id": source_cell,
            "rsrp": serving_rsrp,
            "sinr": serving_sinr,
            "failure_type": failure_type,
            # derived
            "timestamp": ts.isoformat(),
            "source_cell": source_cell,
            "target_cell": target_cell,
            "serving_rsrp": serving_rsrp,
            "target_rsrp": target_rsrp,
            "serving_sinr": serving_sinr,
            "target_sinr": target_sinr,
            "serving_rsrq": serving_rsrq,
            "target_rsrq": target_rsrq,
            "event_type": "HANDOVER",
            "measurement_event": MEASUREMENT_EVENT_MAP.get(failure_type, "A3"),
            "ho_type": HO_TYPE_MAP.get(failure_type, "INTRA_NR"),
            "failure_stage": failure_stage,
            "speed_kmph": _speed_kmph(failure_type, ue_id, int(idx)),
            "beam_id": beam_source,
            "beam_id_target": beam_target,
            "pci_source": pci_source,
            "pci_target": pci_target,
            "time_to_trigger_ms": int(cfg.get("time_to_trigger", 40)),
            "hysteresis_db": float(cfg.get("hysteresis", 0)),
            "xn_latency_ms": _xn_latency_ms(failure_type, ue_id, int(idx)),
            "packet_loss_pct": _packet_loss_pct(failure_type, ue_id),
            "t310_expiry": t310_expiry,
            "rlf_detected": rlf_detected,
            "result": "SUCCESS" if failure_type == "SUCCESS" else "FAILURE",
            "neighbor_relation_status": rel_status,
            "missing_neighbor": missing_nbr,
        }
        scenarios = classify_rca_scenarios(enriched)
        enriched["rca_scenarios"] = "|".join(scenarios) if scenarios else ""
        rows.append(enriched)

    out = pd.DataFrame(rows)
    return out


def aggregate_enriched_kpis(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    """Cell-level KPI rates from enriched handover events."""
    sub = df[df["source_cell"].astype(str) == str(cell_id)]
    if sub.empty:
        sub = df[df["cell_id"].astype(str) == str(cell_id)]
    if sub.empty:
        return {}

    total = len(sub)
    ft = sub["failure_type"].astype(str).str.upper()
    base = {
        "ho_event_count": total,
        "ho_success_rate": _rate((ft == "SUCCESS").sum(), total),
        "ho_prep_fail_rate": _rate((ft == "PREP_FAILURE").sum(), total),
        "ho_exec_fail_rate": _rate((ft.isin(["EXEC_FAILURE", "WRONG_CELL"])).sum(), total),
        "ho_too_late_rate": _rate((ft == "TOO_LATE_HO").sum(), total),
        "ho_too_early_rate": _rate((ft == "TOO_EARLY_HO").sum(), total),
        "ho_ping_pong_rate": _rate((ft == "PING_PONG").sum(), total),
        "ho_wrong_cell_rate": _rate((ft == "WRONG_CELL").sum(), total),
        "ho_xn_fail_rate": _rate((ft == "XN_FAILURE").sum(), total),
        "ho_n2_fail_rate": _rate((ft == "N2_FAILURE").sum(), total),
    }
    non_success = sub[ft != "SUCCESS"]
    base["target_rsrp"] = round(float(non_success["target_rsrp"].mean()), 2) if len(non_success) else None
    base["ss_rsrp"] = round(float(sub["serving_rsrp"].mean()), 2)
    base["ss_sinr"] = round(float(sub["serving_sinr"].mean()), 2)

    def _scenario_rate(tag: str) -> float | None:
        mask = sub["rca_scenarios"].astype(str).str.contains(tag, na=False)
        return _rate(int(mask.sum()), total)

    base.update({
        "ho_post_ho_rlf_rate": _rate(int(sub["rlf_detected"].astype(bool).sum()), total),
        "ho_missing_neighbor_rate": _rate(int(sub["missing_neighbor"].astype(bool).sum()), total),
        "ho_coverage_induced_rate": _scenario_rate("coverage_induced_ho_failure"),
        "ho_interference_induced_rate": _scenario_rate("interference_induced_ho_failure"),
        "ho_beam_instability_rate": _scenario_rate("beam_instability"),
        "ho_mobility_config_rate": _scenario_rate("mobility_configuration_issue"),
        "ho_xn_transport_rate": _scenario_rate("xn_transport_failure"),
        "ho_mean_xn_latency_ms": round(float(sub["xn_latency_ms"].mean()), 1) if "xn_latency_ms" in sub else None,
        "ho_mean_packet_loss_pct": round(float(sub["packet_loss_pct"].mean()), 2) if "packet_loss_pct" in sub else None,
    })
    return {k: v for k, v in base.items() if v is not None}


def _rate(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round(100.0 * num / den, 2)


def write_enriched_handover_csv(
    source: Path | None = None,
    dest: Path | None = None,
) -> Path:
    """Read handover_events.csv and write handover_events_enriched.csv."""
    src = source or dataset_path(DatasetName.HANDOVER_EVENTS)
    dst = dest or (datasets_dir() / "handover_events_enriched.csv")
    raw = pd.read_csv(src)
    enriched = enrich_handover_events(raw)
    dst.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(dst, index=False)
    return dst
