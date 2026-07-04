"""Telecom dataset registry and path resolution."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from tnic.config import get_settings


class DatasetName(str, Enum):
    PM_COUNTERS = "pm_counters"
    HANDOVER_EVENTS = "handover_events"
    RLF_EVENTS = "rlf_events"
    RACH_EVENTS = "rach_events"
    CALL_DROP_EVENTS = "call_drop_events"
    THROUGHPUT_METRICS = "throughput_metrics"


DATASET_FILES: dict[DatasetName, str] = {
    DatasetName.PM_COUNTERS: "pm_counters.csv",
    DatasetName.HANDOVER_EVENTS: "handover_events.csv",
    DatasetName.RLF_EVENTS: "rlf_events.csv",
    DatasetName.RACH_EVENTS: "rach_events.csv",
    DatasetName.CALL_DROP_EVENTS: "call_drop_events.csv",
    DatasetName.THROUGHPUT_METRICS: "throughput_metrics.csv",
}


def datasets_dir() -> Path:
    env = os.environ.get("TNIC_DATASETS_DIR")
    if env:
        return Path(env)
    settings = get_settings()
    candidates = [
        settings.data_dir / "datasets",
        Path(__file__).resolve().parent.parent.parent / "data" / "datasets",
        Path(__file__).resolve().parent.parent.parent.parent / "datasets",
        Path("/workspace/datasets"),
    ]
    for p in candidates:
        if p.exists() and any(p.glob("*.csv")):
            return p
    return candidates[0]


def dataset_path(name: DatasetName) -> Path:
    path = datasets_dir() / DATASET_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return path
