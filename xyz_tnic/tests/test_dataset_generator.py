"""Smoke tests for telecom dataset generator script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "generate_telecom_datasets.py"
DATASETS = ROOT / "datasets"


def test_generator_produces_seven_files_with_rsrq():
    assert GENERATOR.exists()
    subprocess.run(
        [sys.executable, str(GENERATOR), "--out", str(DATASETS), "--no-sync"],
        check=True,
        cwd=str(ROOT),
    )
    expected = [
        "pm_counters.csv",
        "handover_events.csv",
        "rlf_events.csv",
        "rach_events.csv",
        "call_drop_events.csv",
        "throughput_metrics.csv",
    ]
    for name in expected:
        df = pd.read_csv(DATASETS / name)
        assert len(df) >= 1000
        assert "cell_id" in df.columns or name == "throughput_metrics.csv"

    ho = pd.read_csv(DATASETS / "handover_events.csv")
    assert "rsrq" in ho.columns
    assert set(ho["cell_id"].unique()) >= {"XYZ401", "XYZ410"}

    pm = pd.read_csv(DATASETS / "pm_counters.csv")
    for col in ("rsrp", "rsrq", "sinr", "cqi", "ho_attempt", "ho_success", "rach_success"):
        assert col in pm.columns

    inc = pd.read_csv(ROOT / "xyz_tnic" / "data" / "incidents.csv")
    assert len(inc) >= 1000
    assert inc.iloc[0]["incident_id"] == "INC-2026-001"
    assert inc.iloc[0]["issue_type"] == "call_drop"
