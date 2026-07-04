#!/usr/bin/env python3
"""Generate realistic telecom dummy datasets for TNIC demo and RCA agents.

Produces 1000 rows per file with good/medium/bad cell profiles (XYZ401–XYZ410).
"""

from __future__ import annotations

import argparse
import random
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "datasets"
SYNC_TARGETS = [
    ROOT / "backend" / "data" / "datasets",
    ROOT / "xyz_tnic" / "data" / "datasets",
]
INCIDENT_TARGETS = [
    ROOT / "backend" / "data" / "incidents.csv",
    ROOT / "xyz_tnic" / "data" / "incidents.csv",
]

CELLS = [f"XYZ{400 + i}" for i in range(1, 11)]
ROWS = 1000
RNG_SEED = 42

HO_FAILURE_TYPES = [
    "SUCCESS", "TOO_LATE_HO", "TOO_EARLY_HO", "PREP_FAILURE", "PING_PONG",
    "WRONG_CELL", "XN_FAILURE", "N2_FAILURE",
]
RLF_CAUSES = ["Coverage", "Post_HO", "Interference"]
RACH_OUTCOMES = ["SUCCESS", "MSG1", "MSG2", "MSG3", "MSG4"]
DROP_TYPES = ["Mobility", "Radio", "Core", "IMS", "Transport", "None"]
TP_ISSUES = ["Congestion", "RF", "Scheduler", "Backhaul", "None"]
ISSUE_TYPES = [
    "call_drop", "handover", "rach", "rlf", "throughput",
    "latency", "beamforming", "core", "transport",
]
SEVERITIES = ["Critical", "High", "Medium", "Low"]
STATUSES = ["Closed", "Open", "In Progress"]


@dataclass(frozen=True)
class CellProfile:
    tier: str  # good | medium | bad
    rsrp_mean: float
    rsrp_spread: float
    sinr_mean: float
    sinr_spread: float
    cqi_mean: float
    ho_success_pct: float
    rach_success_pct: float
    dl_tp_mean: float
    drop_weight: float
    rlf_weight: float
    primary_issue: str


# Bad: mobility/RACH/RLF/throughput hotspots; good: XYZ409–410
PROFILES: dict[str, CellProfile] = {
    "XYZ401": CellProfile("bad", -118, 6, -2, 8, 5.5, 72, 55, 180, 3.5, 2.8, "call_drop"),
    "XYZ402": CellProfile("bad", -115, 5, 0, 7, 6.0, 78, 48, 210, 2.5, 2.0, "rach"),
    "XYZ403": CellProfile("bad", -116, 5, -1, 7, 5.8, 75, 58, 195, 2.8, 3.2, "rlf"),
    "XYZ404": CellProfile("bad", -112, 4, 2, 6, 6.5, 80, 62, 120, 2.0, 1.5, "throughput"),
    "XYZ405": CellProfile("medium", -108, 4, 5, 5, 8.0, 86, 72, 320, 1.5, 1.2, "handover"),
    "XYZ406": CellProfile("medium", -106, 4, 7, 5, 9.0, 88, 78, 380, 1.2, 1.0, "handover"),
    "XYZ407": CellProfile("medium", -105, 3, 8, 4, 9.5, 90, 80, 420, 1.0, 0.9, "mobility"),
    "XYZ408": CellProfile("medium", -103, 3, 10, 4, 10.5, 92, 85, 480, 0.8, 0.7, "core"),
    "XYZ409": CellProfile("good", -92, 3, 16, 3, 13.0, 97, 94, 620, 0.3, 0.2, "None"),
    "XYZ410": CellProfile("good", -88, 2, 20, 3, 14.5, 98, 96, 710, 0.2, 0.15, "None"),
}


def _rsrq_from_rsrp_sinr(rsrp: float, sinr: float) -> float:
    """Approximate SS-RSRQ (dB) from RSRP and SINR for synthetic data."""
    base = -12.0 + (rsrp + 100) * 0.05 + sinr * 0.15
    return round(max(-20.0, min(-3.0, base + random.gauss(0, 1.2))), 1)


def _rf_triplet(profile: CellProfile) -> tuple[float, float, float]:
    rsrp = round(random.gauss(profile.rsrp_mean, profile.rsrp_spread), 1)
    sinr = round(random.gauss(profile.sinr_mean, profile.sinr_spread), 1)
    rsrq = _rsrq_from_rsrp_sinr(rsrp, sinr)
    return rsrp, rsrq, sinr


def _iter_cells(n: int) -> list[str]:
    """Round-robin cell IDs so each cell gets n // len(CELLS) rows (+ remainder)."""
    out: list[str] = []
    while len(out) < n:
        for cell in CELLS:
            out.append(cell)
            if len(out) >= n:
                break
    return out


def _pick_cell(weights: dict[str, float] | None = None) -> str:
    if weights:
        cells, w = zip(*weights.items())
        return random.choices(cells, weights=w, k=1)[0]
    return random.choice(CELLS)


def _ue_id(n: int) -> str:
    return f"UE{10000 + n}"


def generate_pm_counters() -> pd.DataFrame:
    random.seed(RNG_SEED)
    start = datetime(2026, 7, 1)
    records: list[dict] = []
    idx = 0
    # 100 hourly buckets × 10 cells = 1000 rows
    for hour in range(100):
        ts = start + timedelta(hours=hour)
        for cell in CELLS:
            p = PROFILES[cell]
            ho_att = random.randint(800, 2200)
            ho_succ = min(ho_att, int(ho_att * random.gauss(p.ho_success_pct / 100, 0.03)))
            rach_att = random.randint(180, 900)
            rach_succ = min(rach_att, int(rach_att * random.gauss(p.rach_success_pct / 100, 0.04)))
            rsrp, rsrq, sinr = _rf_triplet(p)
            cqi = max(1, min(15, int(round(random.gauss(p.cqi_mean, 1.5)))))
            dl = max(40, round(random.gauss(p.dl_tp_mean, p.dl_tp_mean * 0.12)))
            ul = max(10, round(dl * random.uniform(0.08, 0.22)))
            records.append({
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "cell_id": cell,
                "ho_attempt": ho_att,
                "rach_attempt": rach_att,
                "dl_tp": dl,
                "ul_tp": ul,
                "cqi": cqi,
                "ho_success": ho_succ,
                "rach_success": rach_succ,
                "rsrp": rsrp,
                "rsrq": rsrq,
                "sinr": sinr,
            })
            idx += 1
            if idx >= ROWS:
                break
        if idx >= ROWS:
            break
    return pd.DataFrame(records[:ROWS])


def _ho_failure(profile: CellProfile, rsrp: float, sinr: float) -> str:
    roll = random.random()
    success_p = profile.ho_success_pct / 100
    if roll < success_p:
        if sinr > 14 and rsrp > -95 and random.random() < 0.04:
            return "TOO_EARLY_HO"
        return "SUCCESS"
    fail_roll = random.random()
    if profile.tier == "bad":
        if fail_roll < 0.22:
            return "TOO_LATE_HO"
        if fail_roll < 0.35:
            return "PREP_FAILURE"
        if fail_roll < 0.48:
            return "WRONG_CELL"
        if fail_roll < 0.62:
            return "PING_PONG"
        if fail_roll < 0.78:
            return "XN_FAILURE"
        return "N2_FAILURE"
    if fail_roll < 0.35:
        return "TOO_LATE_HO"
    if fail_roll < 0.55:
        return "PREP_FAILURE"
    if fail_roll < 0.70:
        return "PING_PONG"
    if fail_roll < 0.85:
        return "XN_FAILURE"
    return "N2_FAILURE"


def generate_handover_events() -> pd.DataFrame:
    random.seed(RNG_SEED + 1)
    rows = []
    for i, cell in enumerate(_iter_cells(ROWS)):
        p = PROFILES[cell]
        rsrp, rsrq, sinr = _rf_triplet(p)
        rows.append({
            "ue_id": _ue_id(i),
            "cell_id": cell,
            "rsrp": rsrp,
            "rsrq": rsrq,
            "sinr": sinr,
            "failure_type": _ho_failure(p, rsrp, sinr),
        })
    return pd.DataFrame(rows)


def _rlf_cause(profile: CellProfile, rsrp: float, sinr: float) -> str:
    if rsrp <= -112:
        return "Coverage"
    if sinr <= 0:
        return "Interference"
    if profile.tier == "bad" and random.random() < 0.45:
        return "Post_HO"
    return random.choice(RLF_CAUSES)


def generate_rlf_events() -> pd.DataFrame:
    random.seed(RNG_SEED + 2)
    rows = []
    for i, cell in enumerate(_iter_cells(ROWS)):
        p = PROFILES[cell]
        rsrp, rsrq, sinr = _rf_triplet(p)
        if p.tier == "good" and random.random() < 0.85:
            cause = "None"
        else:
            cause = _rlf_cause(p, rsrp, sinr)
        rows.append({
            "ue_id": _ue_id(i + 500),
            "cell_id": cell,
            "rsrp": rsrp,
            "rsrq": rsrq,
            "sinr": sinr,
            "cause": cause,
        })
    return pd.DataFrame(rows)


def _rach_outcome(profile: CellProfile) -> str:
    roll = random.random()
    if roll < profile.rach_success_pct / 100:
        return "SUCCESS"
    fail = random.random()
    if profile.tier == "bad":
        if fail < 0.30:
            return "MSG3"
        if fail < 0.55:
            return "MSG1"
        if fail < 0.75:
            return "MSG2"
        return "MSG4"
    if fail < 0.40:
        return "MSG1"
    if fail < 0.65:
        return "MSG2"
    if fail < 0.85:
        return "MSG3"
    return "MSG4"


def generate_rach_events() -> pd.DataFrame:
    random.seed(RNG_SEED + 3)
    rows = []
    seen: set[tuple[str, str, str]] = set()
    i = 0
    for cell in _iter_cells(ROWS):
        p = PROFILES[cell]
        rsrp, rsrq, sinr = _rf_triplet(p)
        outcome = _rach_outcome(p)
        ue = _ue_id(i)
        key = (ue, cell, outcome)
        if key in seen:
            i += 1
            continue
        seen.add(key)
        rows.append({
            "ue_id": ue,
            "cell_id": cell,
            "rsrp": rsrp,
            "rsrq": rsrq,
            "sinr": sinr,
            "msg_failure": outcome,
        })
        i += 1
    return pd.DataFrame(rows)


def _drop_type(profile: CellProfile) -> str:
    if profile.tier == "good":
        return "None" if random.random() < 0.92 else random.choice(["Radio", "Core"])
    if profile.tier == "medium":
        return "None" if random.random() < 0.75 else random.choice(DROP_TYPES[:-1])
    if profile.primary_issue == "call_drop":
        return random.choices(DROP_TYPES[:-1], weights=[45, 25, 10, 10, 10], k=1)[0]
    if profile.primary_issue == "mobility":
        return random.choices(DROP_TYPES[:-1], weights=[50, 20, 10, 10, 10], k=1)[0]
    return "None" if random.random() < 0.5 else random.choice(DROP_TYPES[:-1])


def generate_call_drop_events() -> pd.DataFrame:
    random.seed(RNG_SEED + 4)
    rows = []
    seen: set[tuple[str, str, str]] = set()
    i = 0
    for cell in _iter_cells(ROWS):
        p = PROFILES[cell]
        rsrp, rsrq, sinr = _rf_triplet(p)
        drop = _drop_type(p)
        ue = _ue_id(i + 2000)
        key = (ue, cell, drop)
        if key in seen:
            i += 1
            continue
        seen.add(key)
        rows.append({
            "ue_id": ue,
            "cell_id": cell,
            "rsrp": rsrp,
            "rsrq": rsrq,
            "sinr": sinr,
            "drop_type": drop,
        })
        i += 1
    return pd.DataFrame(rows)


def _throughput_issue(profile: CellProfile, cqi: float, prb: float, dl: float) -> str:
    if profile.primary_issue == "throughput" and random.random() < 0.55:
        return random.choice(["RF", "Backhaul", "Scheduler"])
    if prb >= 82:
        return "Congestion"
    if cqi <= 6:
        return "RF"
    if dl < profile.dl_tp_mean * 0.55:
        return "Backhaul"
    if prb >= 55:
        return "Scheduler"
    return "None"


def generate_throughput_metrics() -> pd.DataFrame:
    random.seed(RNG_SEED + 5)
    rows = []
    for i in range(ROWS):
        cell = CELLS[i % len(CELLS)]
        p = PROFILES[cell]
        cqi = max(1, min(15, round(random.gauss(p.cqi_mean, 1.8), 1)))
        prb = round(max(5, min(98, random.gauss(45 if p.tier == "good" else 62, 18))), 1)
        dl = max(30, round(random.gauss(p.dl_tp_mean, p.dl_tp_mean * 0.18)))
        _, rsrq, sinr = _rf_triplet(p)
        rows.append({
            "cell_id": cell,
            "cqi": cqi,
            "prb_util": prb,
            "dl_tp": dl,
            "rsrq": rsrq,
            "sinr": sinr,
            "issue": _throughput_issue(p, cqi, prb, dl),
        })
    return pd.DataFrame(rows)


def generate_incidents() -> pd.DataFrame:
    random.seed(RNG_SEED + 6)
    summaries = {
        "call_drop": "Voice drops during mobility on {cell}",
        "handover": "HO prep/exec failure spike neighbor sector {cell}",
        "rach": "Registration failures at cell edge {cell}",
        "rlf": "RLF cluster after successful HO on {cell}",
        "throughput": "DL speed below SLA on {cell}",
        "latency": "Video buffering on 5QI-9 during peak {cell}",
        "beamforming": "Beam failure ratio above threshold {cell}",
        "core": "PDU session release without RF anomaly {cell}",
        "transport": "N3 throughput cap during evening peak {cell}",
    }
    causes = {
        "call_drop": "Missed Xn neighbor relation for inter-gNB HO",
        "handover": "Target cell barred due to transport alarm on F1",
        "rach": "PRACH occasion collision with co-channel DAS",
        "rlf": "Too-late HO — A3 offset insufficient for fast UE",
        "throughput": "High DL BLER and rank-1 stuck — interferer on n77",
        "latency": "UPF cluster CPU saturation",
        "beamforming": "SSB beam weight drift after AAU firmware upgrade",
        "core": "AMF subscription profile missing DNN",
        "transport": "Backhaul link at high utilization on core switch",
    }
    resolutions = [
        "Added neighbor relation and tuned HO margins",
        "Restored F1 link and cleared cell barring",
        "Adjusted PRACH configuration index and root sequence",
        "Reduced A3 offset and enabled time-to-trigger tuning",
        "Retuned electrical tilt and enabled IRC",
        "Rebalanced UPF sessions and scaled pod count",
        "Re-ran beam calibration procedure",
        "Updated UDM subscription template",
        "Enabled QoS shaping and scheduled backhaul upgrade",
    ]
    start = datetime(2026, 1, 1, 8, 0, 0)
    rows = []
    # Deterministic first incident for tests / demos
    rows.append({
        "incident_id": "INC-2026-001",
        "opened_at": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "cell_id": "XYZ401",
        "issue_type": "call_drop",
        "complaint_summary": summaries["call_drop"].format(cell="XYZ401"),
        "root_cause": causes["call_drop"],
        "resolution": resolutions[0],
        "status": "Closed",
        "severity": "High",
    })
    for i in range(1, ROWS):
        cell = _pick_cell({c: (3 if PROFILES[c].tier == "bad" else 0.5 if PROFILES[c].tier == "good" else 1) for c in CELLS})
        issue = PROFILES[cell].primary_issue if PROFILES[cell].primary_issue != "None" and random.random() < 0.6 else random.choice(ISSUE_TYPES)
        opened = start + timedelta(hours=i * 7 + random.randint(0, 5))
        tier = PROFILES[cell].tier
        sev = {"bad": "High", "medium": "Medium", "good": "Low"}[tier]
        if random.random() < 0.15:
            sev = "Critical"
        rows.append({
            "incident_id": f"INC-2026-{i + 1:03d}",
            "opened_at": opened.strftime("%Y-%m-%dT%H:%M:%S"),
            "cell_id": cell,
            "issue_type": issue,
            "complaint_summary": summaries.get(issue, "Network issue on {cell}").format(cell=cell),
            "root_cause": causes.get(issue, "Under investigation"),
            "resolution": random.choice(resolutions),
            "status": random.choices(STATUSES, weights=[75, 15, 10], k=1)[0],
            "severity": sev if sev in SEVERITIES else random.choice(SEVERITIES),
        })
    return pd.DataFrame(rows)


def write_all(out_dir: Path, sync: bool = True) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    datasets = {
        "pm_counters.csv": generate_pm_counters(),
        "handover_events.csv": generate_handover_events(),
        "rlf_events.csv": generate_rlf_events(),
        "rach_events.csv": generate_rach_events(),
        "call_drop_events.csv": generate_call_drop_events(),
        "throughput_metrics.csv": generate_throughput_metrics(),
    }
    counts: dict[str, int] = {}
    for name, df in datasets.items():
        path = out_dir / name
        df.to_csv(path, index=False)
        counts[name] = len(df)
        print(f"  wrote {path.name}: {len(df)} rows, cols={list(df.columns)}")

    incidents = generate_incidents()
    inc_path = out_dir.parent / "incidents.csv" if out_dir.name == "datasets" else out_dir / "incidents.csv"
    # canonical incidents live next to datasets folder
    if out_dir.name == "datasets":
        for target in INCIDENT_TARGETS:
            target.parent.mkdir(parents=True, exist_ok=True)
            incidents.to_csv(target, index=False)
            print(f"  wrote {target}: {len(incidents)} rows")
        counts["incidents.csv"] = len(incidents)
    else:
        incidents.to_csv(inc_path, index=False)
        counts["incidents.csv"] = len(incidents)

    if sync and out_dir == DEFAULT_OUT:
        for target in SYNC_TARGETS:
            target.mkdir(parents=True, exist_ok=True)
            for name in datasets:
                shutil.copy2(out_dir / name, target / name)
            print(f"  synced datasets -> {target}")

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate telecom dummy datasets")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory")
    parser.add_argument("--no-sync", action="store_true", help="Skip copying to backend/xyz_tnic")
    args = parser.parse_args()
    print(f"Generating {ROWS} rows per dataset -> {args.out}")
    counts = write_all(args.out, sync=not args.no_sync)
    print("Done:", counts)


if __name__ == "__main__":
    main()
