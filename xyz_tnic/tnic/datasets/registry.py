"""Telecom dataset registry and path resolution."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from tnic.config import get_settings


class DatasetName(str, Enum):
    PM_COUNTERS = "pm_counters"
    HANDOVER_EVENTS = "handover_events"
    HANDOVER_EVENTS_ENRICHED = "handover_events_enriched"
    RLF_EVENTS = "rlf_events"
    RACH_EVENTS = "rach_events"
    CALL_DROP_EVENTS = "call_drop_events"
    THROUGHPUT_METRICS = "throughput_metrics"
    # Core assurance datasets
    GNB_SYSLOG = "gnb_syslog"
    CELL_CONFIGURATION = "cell_configuration"
    NEIGHBOR_RELATIONS = "neighbor_relations"
    ANR_EVENTS = "anr_events"
    VONR_SESSIONS = "vonr_sessions"
    ALARM_EVENTS = "alarm_events"
    UE_PROTOCOL_TRACE = "ue_protocol_trace"
    TELECOM_ISSUES = "telecom_issues"


DATASET_FILES: dict[DatasetName, str] = {
    DatasetName.PM_COUNTERS: "pm_counters.csv",
    DatasetName.HANDOVER_EVENTS: "handover_events.csv",
    DatasetName.HANDOVER_EVENTS_ENRICHED: "handover_events_enriched.csv",
    DatasetName.RLF_EVENTS: "rlf_events.csv",
    DatasetName.RACH_EVENTS: "rach_events.csv",
    DatasetName.CALL_DROP_EVENTS: "call_drop_events.csv",
    DatasetName.THROUGHPUT_METRICS: "throughput_metrics.csv",
    DatasetName.GNB_SYSLOG: "gnb_syslog.csv",
    DatasetName.CELL_CONFIGURATION: "cell_configuration.csv",
    DatasetName.NEIGHBOR_RELATIONS: "neighbor_relations.csv",
    DatasetName.ANR_EVENTS: "anr_events.csv",
    DatasetName.VONR_SESSIONS: "vonr_sessions.csv",
    DatasetName.ALARM_EVENTS: "alarm_events.csv",
    DatasetName.UE_PROTOCOL_TRACE: "ue_protocol_trace.csv",
    DatasetName.TELECOM_ISSUES: "telecom_issues.csv",
}

ASSURANCE_DATASETS = frozenset({
    DatasetName.GNB_SYSLOG,
    DatasetName.CELL_CONFIGURATION,
    DatasetName.NEIGHBOR_RELATIONS,
    DatasetName.ANR_EVENTS,
    DatasetName.VONR_SESSIONS,
    DatasetName.UE_PROTOCOL_TRACE,
})


def datasets_dir() -> Path:
    env = os.environ.get("TNIC_DATASETS_DIR")
    if env:
        return Path(env)
    settings = get_settings()
    candidates = [
        Path("/workspace/datasets"),
        Path(__file__).resolve().parent.parent.parent.parent / "datasets",  # repo root when rootDir=backend
        settings.data_dir / "datasets",
        Path(__file__).resolve().parent.parent.parent / "data" / "datasets",
    ]
    # Prefer directory with core assurance datasets
    for p in candidates:
        if p.exists() and (p / "gnb_syslog.csv").exists():
            return p
    for p in candidates:
        if p.exists() and any(p.glob("*.csv")):
            return p
    return candidates[0]


def dataset_path(name: DatasetName) -> Path:
    path = datasets_dir() / DATASET_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return path
