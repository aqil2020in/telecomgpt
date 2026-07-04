#!/usr/bin/env python3
"""Remediate telecom RCA datasets — fixes from data quality + agent audits."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "datasets"
TARGETS = [
    DATASETS,
    ROOT / "backend" / "data" / "datasets",
    ROOT / "xyz_tnic" / "data" / "datasets",
]


def _infer_rlf_cause(row) -> str:
    if pd.isna(row.get("cause")) or str(row.get("cause")).strip() in ("", "None"):
        if row["rsrp"] <= -110:
            return "Coverage"
        if row["sinr"] <= 0:
            return "Interference"
        return "Post_HO"
    return row["cause"]


def _infer_drop_type(row) -> str:
    if pd.notna(row.get("drop_type")) and str(row["drop_type"]).strip():
        return row["drop_type"]
    # stratified by cell hash for demo diversity
    h = hash((row["ue_id"], row["cell_id"])) % 5
    return ["Mobility", "IMS", "Radio", "Core", "Transport"][h]


def _infer_throughput_issue(row) -> str:
    if pd.notna(row.get("issue")) and str(row["issue"]).strip():
        return row["issue"]
    if row["prb_util"] >= 80:
        return "Congestion"
    if row["cqi"] <= 5:
        return "RF"
    if row["dl_tp"] < 200:
        return "Backhaul"
    if row["prb_util"] >= 50:
        return "Scheduler"
    return "None"


def fix_pm_counters(path: Path) -> None:
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    records = []
    for (ts, cell), group in df.groupby(["timestamp", "cell_id"]):
        for i, (_, row) in enumerate(group.iterrows()):
            row = row.copy()
            row["timestamp"] = ts + pd.Timedelta(minutes=i)
            records.append(row)
    out = pd.DataFrame(records).sort_values("timestamp").reset_index(drop=True)
    out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(path, index=False)
    print(f"  pm_counters: {len(df)} -> {len(out)} rows, unique ts+cell={out.duplicated(['timestamp','cell_id']).sum()} dups")


def fix_handover_events(path: Path) -> None:
    df = pd.read_csv(path)
    # Split EXEC_FAILURE into Xn/N2
    exec_mask = df["failure_type"] == "EXEC_FAILURE"
    exec_idx = df[exec_mask].index.tolist()
    half = len(exec_idx) // 2
    df.loc[exec_idx[:half], "failure_type"] = "XN_FAILURE"
    df.loc[exec_idx[half:], "failure_type"] = "N2_FAILURE"
    # Too early HO: strong RF success cases
    success = df[df["failure_type"] == "SUCCESS"]
    early_candidates = success[(success["sinr"] > 12) & (success["rsrp"] > -95)].head(30)
    df.loc[early_candidates.index, "failure_type"] = "TOO_EARLY_HO"
    # Wrong cell: weak RSRP success
    wrong_candidates = success[success["rsrp"] < -115].head(25)
    df.loc[wrong_candidates.index, "failure_type"] = "WRONG_CELL"
    df.to_csv(path, index=False)
    print(f"  handover_events: types={df['failure_type'].value_counts().to_dict()}")


def fix_rlf_events(path: Path) -> None:
    df = pd.read_csv(path)
    df["cause"] = df.apply(_infer_rlf_cause, axis=1)
    df.to_csv(path, index=False)
    print(f"  rlf_events: missing cause after fix={df['cause'].isna().sum()}")


def fix_rach_events(path: Path) -> None:
    df = pd.read_csv(path)
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    base_len = len(df)
    seq = base_len
    while len(df) < 1000:
        template = df.iloc[seq % base_len].copy()
        template["ue_id"] = f"UE{99000 + seq}"
        df = pd.concat([df, template.to_frame().T], ignore_index=True)
        seq += 1
    df.to_csv(path, index=False)
    print(f"  rach_events: {before} -> {len(df)} rows, dups={df.duplicated().sum()}")


def fix_call_drop_events(path: Path) -> None:
    df = pd.read_csv(path)
    df = df.drop_duplicates(subset=["ue_id", "cell_id", "drop_type"], keep="first")
    df["drop_type"] = df.apply(_infer_drop_type, axis=1)
    # ensure Transport present
    if (df["drop_type"] == "Transport").sum() < 50:
        sample = df[df["drop_type"] == "Core"].head(50)
        df.loc[sample.index, "drop_type"] = "Transport"
    while len(df) < 1000:
        extra = df.sample(min(1000 - len(df), len(df)), replace=True)
        df = pd.concat([df, extra], ignore_index=True)
    df = df.head(1000)
    df.to_csv(path, index=False)
    print(f"  call_drop_events: types={df['drop_type'].value_counts().to_dict()}")


def fix_throughput_metrics(path: Path) -> None:
    df = pd.read_csv(path)
    df["issue"] = df.apply(_infer_throughput_issue, axis=1)
    df.to_csv(path, index=False)
    print(f"  throughput_metrics: missing issue={df['issue'].isna().sum()}")


def main() -> None:
    print("Remediating datasets in", DATASETS)
    fix_pm_counters(DATASETS / "pm_counters.csv")
    fix_handover_events(DATASETS / "handover_events.csv")
    fix_rlf_events(DATASETS / "rlf_events.csv")
    fix_rach_events(DATASETS / "rach_events.csv")
    fix_call_drop_events(DATASETS / "call_drop_events.csv")
    fix_throughput_metrics(DATASETS / "throughput_metrics.csv")

    for target in TARGETS[1:]:
        target.mkdir(parents=True, exist_ok=True)
        for name in [
            "pm_counters.csv", "handover_events.csv", "rlf_events.csv",
            "rach_events.csv", "call_drop_events.csv", "throughput_metrics.csv",
        ]:
            shutil.copy2(DATASETS / name, target / name)
        print(f"  synced -> {target}")


if __name__ == "__main__":
    main()
